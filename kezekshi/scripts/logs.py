#!/usr/bin/env python3
"""Бэкенд логтарын іздеу. Тек оқу.

Екі жол (бірінші қолжетімдісі қолданылады):
  1. juz40-vpn-logs сервисі — VPN керек емес, кезекшілерге ыңғайлы:
       LOGS_SERVICE_URL=https://<logs-host>  LOGS_SERVICE_TOKEN=<bearer токен>
  2. Kibana тікелей — VPN керек:
       KIBANA_URL=http://<kibana-host>:5601  [KIBANA_AUTH="Basic ..." | "ApiKey ..."]

Мысалдар:
  logs.py --check
  logs.py --request-id 799b789358c3300730d44c350291afeb
  logs.py --user someone@gmail.com --at "2026-11-18 14:20" --minutes 15 --errors
  logs.py --mapping "/v1/unts/{id}/start" --since 1h --errors --count-users

Шығарылатын өрістер: уақыт (Алматы), level, статус, метод, endpoint, requestId, username,
duration, message (қысқартылған). Сұраныс/жауап денесі ЕШҚАШАН шығарылмайды.
"""
import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

INDEX = "logs-*-*,logs-*,filebeat-*"
ALMATY = timezone(timedelta(hours=5))
SAFE_FIELDS = [
    "@timestamp",
    "parsed_json.level",
    "parsed_json.responseStatusCode",
    "parsed_json.requestHttpMethod",
    "parsed_json.requestMapping",
    "parsed_json.requestUri",
    "parsed_json.requestId",
    "parsed_json.username",
    "parsed_json.userRoles",
    "parsed_json.duration",
    "parsed_json.message",
    "parsed_json.X-Device-Name",
    "parsed_json.app-version",
]
SECRET_RE = re.compile(r'("?(password|token|authorization|secret|code)"?\s*[:=]\s*)("[^"]*"|\S+)', re.I)


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def backend():
    if os.environ.get("LOGS_SERVICE_URL") and os.environ.get("LOGS_SERVICE_TOKEN"):
        return "service"
    if os.environ.get("KIBANA_URL"):
        return "kibana"
    die("Логтарға жол берілмеген. Не LOGS_SERVICE_URL + LOGS_SERVICE_TOKEN (juz40-vpn-logs), "
        "не KIBANA_URL (VPN қосулы болсын) керек.", 3)


def ssl_context():
    # python.org-тың macOS нұсқасы жүйелік сертификаттарды көрмейді — бар болса certifi қолданамыз.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def http(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context()) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            die(f"Логтар рұқсат бермеді ({e.code}): токен/рұқсат керек — әзірлеушіге/DevOps-қа жүгініңіз.", 4)
        if e.code in (502, 503):
            die("Лог сервисі Elasticsearch-ке жете алмады (VPN туннелі түсіп қалған болуы мүмкін).", 2)
        die(f"Логтар қатесі {e.code}: {e.read()[:300]!r}", 1)
    except OSError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            die("SSL сертификаты тексерілмеді. Орнатыңыз: pip3 install certifi "
                "(немесе /Applications/Python 3.x/Install Certificates.command).", 2)
        die(f"Логтарға қосылу мүмкін болмады ({e}). VPN/сервис қолжетімді ме?", 2)


# ---------- уақыт ----------

def parse_since(value):
    m = re.fullmatch(r"(\d+)([mhd])", value)
    if not m:
        die("--since форматы: 30m, 2h, 3d")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(minutes=n) if unit == "m" else timedelta(hours=n) if unit == "h" else timedelta(days=n)


def time_range(args):
    now = datetime.now(timezone.utc)
    if args.at:
        try:
            at = datetime.strptime(args.at, "%Y-%m-%d %H:%M").replace(tzinfo=ALMATY)
        except ValueError:
            die('--at форматы: "YYYY-MM-DD HH:MM" (Алматы уақыты)')
        delta = timedelta(minutes=args.minutes)
        return at - delta, at + delta
    since = parse_since(args.since or ("7d" if args.request_id else "24h"))
    return now - since, now


# ---------- Kibana ----------

def kibana_request(method, path, body=None):
    headers = {"kbn-xsrf": "true", "Content-Type": "application/json"}
    if os.environ.get("KIBANA_AUTH"):
        headers["Authorization"] = os.environ["KIBANA_AUTH"]
    return http(method, os.environ["KIBANA_URL"].rstrip("/") + path, headers, body)


def kibana_search(args, start, end):
    filters = [{"range": {"@timestamp": {"gte": start.isoformat(), "lte": end.isoformat()}}}]
    for value, field in ((args.request_id, "requestId"), (args.user, "username"),
                         (args.mapping, "requestMapping"), (args.text, "message")):
        if value:
            filters.append({"match_phrase": {f"parsed_json.{field}": value}})
    query = {"bool": {"filter": filters}}
    if args.errors:
        query["bool"]["should"] = [
            {"range": {"parsed_json.responseStatusCode": {"gte": 400}}},
            {"terms": {"parsed_json.level": ["ERROR", "WARN", "error", "warn"]}},
        ]
        query["bool"]["minimum_should_match"] = 1
    body = {"size": args.size, "sort": [{"@timestamp": {"order": "desc"}}], "track_total_hits": True,
            "query": query, "_source": SAFE_FIELDS}
    path = "/api/console/proxy?" + urllib.parse.urlencode({"path": f"{INDEX}/_search", "method": "POST"})
    res = kibana_request("POST", path, body)
    hits = []
    for h in res.get("hits", {}).get("hits", []):
        src = h.get("_source", {})
        pj = src.get("parsed_json") or {}
        hits.append({
            "timestamp": src.get("@timestamp"),
            "level": pj.get("level"),
            "status": pj.get("responseStatusCode"),
            "method": pj.get("requestHttpMethod"),
            "uri": pj.get("requestMapping") or pj.get("requestUri"),
            "username": pj.get("username"),
            "duration": pj.get("duration"),
            "requestId": pj.get("requestId"),
            "message": pj.get("message"),
        })
    return res.get("hits", {}).get("total", {}).get("value", len(hits)), hits


# ---------- juz40-vpn-logs ----------

def qs_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def service_search(args, start, end):
    parts = []
    for value, field in ((args.request_id, "requestId"), (args.user, "username"),
                         (args.mapping, "requestMapping"), (args.text, "message")):
        if value:
            parts.append(f"parsed_json.{field}:{qs_quote(value)}")
    if args.errors:
        parts.append("(parsed_json.responseStatusCode:>=400 OR parsed_json.level:(ERROR OR WARN))")
    params = {"q": " AND ".join(parts), "from": start.isoformat(), "to": end.isoformat(), "size": str(args.size)}
    url = os.environ["LOGS_SERVICE_URL"].rstrip("/") + "/logs/search?" + urllib.parse.urlencode(params)
    res = http("GET", url, {"Authorization": f"Bearer {os.environ['LOGS_SERVICE_TOKEN']}"})
    if not isinstance(res, dict) or not isinstance(res.get("hits"), list):
        die("Лог сервисі күтпеген формат қайтарды.", 1)
    hits = [{
        "timestamp": h.get("timestamp"),
        "level": None,
        "status": h.get("status"),
        "method": h.get("method"),
        "uri": h.get("uri"),
        "username": h.get("username"),
        "duration": None,
        "requestId": h.get("requestId"),
        "message": h.get("message"),
    } for h in res["hits"]]  # raw өрісі әдейі алынбайды — онда сұраныс денесі болуы мүмкін
    return res.get("total", len(hits)), hits


# ---------- шығару ----------

def mask(text):
    return SECRET_RE.sub(lambda m: m.group(1) + "***", text)


def fmt_hit(h):
    ts = h.get("timestamp") or ""
    try:
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ALMATY).strftime("%d.%m %H:%M:%S")
    except ValueError:
        pass
    msg = " ".join(str(h.get("message") or "").split())
    if msg == "Request info":
        msg = ""
    parts = [
        ts,
        str(h.get("level") or ""),
        str(h.get("status") or ""),
        f'{h.get("method") or ""} {h.get("uri") or ""}'.strip(),
        f'user={h["username"]}' if h.get("username") else "",
        f'{h["duration"]}ms' if h.get("duration") is not None else "",
        f'req={h["requestId"]}' if h.get("requestId") else "",
        mask(msg[:300]),
    ]
    return " | ".join(p for p in parts if p)


def main():
    p = argparse.ArgumentParser(description="Бэкенд логтарын іздеу (тек оқу)")
    p.add_argument("--check", action="store_true", help="логтар қолжетімді ме")
    p.add_argument("--request-id")
    p.add_argument("--user", help="username / почта")
    p.add_argument("--mapping", help='endpoint үлгісі, мысалы "/v1/unts/{id}/start"')
    p.add_argument("--text", help="message ішіндегі фраза")
    p.add_argument("--at", help='Алматы уақыты "YYYY-MM-DD HH:MM"')
    p.add_argument("--minutes", type=int, default=15, help="--at айналасындағы терезе (±мин)")
    p.add_argument("--since", help="соңғы кезең: 30m, 2h, 3d (әдепкі 24h, request-id үшін 7d)")
    p.add_argument("--errors", action="store_true", help="тек 4xx/5xx және ERROR/WARN")
    p.add_argument("--count-users", action="store_true", help="қанша бөлек пайдаланушы (почталарсыз)")
    p.add_argument("--size", type=int, default=30)
    args = p.parse_args()
    mode = backend()

    if args.check:
        if mode == "service":
            res = http("GET", os.environ["LOGS_SERVICE_URL"].rstrip("/") + "/health", {})
            print(f"OK (juz40-vpn-logs): {json.dumps(res, ensure_ascii=False)[:200]}")
        else:
            st = kibana_request("GET", "/api/status")
            print(f'OK (Kibana): {st.get("name")} {st.get("version", {}).get("number")}')
        return
    if not (args.request_id or args.user or args.mapping or args.text):
        die("Кемінде біреуі керек: --request-id, --user, --mapping немесе --text")
    if args.count_users:
        args.size = max(args.size, 500)

    start, end = time_range(args)
    total, hits = (service_search if mode == "service" else kibana_search)(args, start, end)
    period = f"{start.astimezone(ALMATY):%d.%m %H:%M} — {end.astimezone(ALMATY):%d.%m %H:%M}"

    if args.count_users:
        # Ауқымды бағалау: тек сандар, басқа пайдаланушылардың почталары шығарылмайды.
        users = {h.get("username") for h in hits} - {None, "", "anonymousUser"}
        statuses = {}
        for h in hits:
            if h.get("status") is not None:
                statuses[h["status"]] = statuses.get(h["status"], 0) + 1
        print(f"Кезең (Алматы): {period}; жазба: {total}")
        print(f"Бөлек пайдаланушылар (алғашқы {len(hits)} жазба бойынша): {len(users)}")
        print("Статустар: " + ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items(), key=str)))
        return

    print(f"Кезең (Алматы): {period}; табылды: {total}, көрсетілді: {len(hits)} [{mode}]")
    for h in hits:
        print(fmt_hit(h))


if __name__ == "__main__":
    main()
