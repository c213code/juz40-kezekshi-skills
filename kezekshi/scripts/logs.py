#!/usr/bin/env python3
"""Бэкенд логтарын Kibana (Elasticsearch) арқылы іздеу. Тек оқу.

Kibana мекенжайы KIBANA_URL ортасының айнымалысынан алынады (мысалы http://<kibana-host>:5601).
Kibana-да авторизация қосылса, KIBANA_AUTH="Basic ..." немесе "ApiKey ..." беріледі.

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


def kibana_url():
    url = os.environ.get("KIBANA_URL", "").rstrip("/")
    if not url:
        die("KIBANA_URL берілмеген. Мысалы: export KIBANA_URL=http://<kibana-host>:5601 (VPN қосулы болсын)", 3)
    return url


def request(method, path, body=None):
    headers = {"kbn-xsrf": "true", "Content-Type": "application/json"}
    auth = os.environ.get("KIBANA_AUTH")
    if auth:
        headers["Authorization"] = auth
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(kibana_url() + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            die(f"Kibana рұқсат бермеді ({e.code}). KIBANA_AUTH керек — әзірлеушіге/DevOps-қа жүгініңіз.", 4)
        die(f"Kibana қатесі {e.code}: {e.read()[:300]!r}", 1)
    except OSError as e:
        die(f"Kibana-ға қосылу мүмкін болмады ({e}). VPN қосулы ма?", 2)


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


def build_query(args):
    start, end = time_range(args)
    filters = [{"range": {"@timestamp": {"gte": start.isoformat(), "lte": end.isoformat()}}}]
    if args.request_id:
        filters.append({"match_phrase": {"parsed_json.requestId": args.request_id}})
    if args.user:
        filters.append({"match_phrase": {"parsed_json.username": args.user}})
    if args.mapping:
        filters.append({"match_phrase": {"parsed_json.requestMapping": args.mapping}})
    if args.text:
        filters.append({"match_phrase": {"parsed_json.message": args.text}})
    query = {"bool": {"filter": filters}}
    if args.errors:
        query["bool"]["should"] = [
            {"range": {"parsed_json.responseStatusCode": {"gte": 400}}},
            {"terms": {"parsed_json.level": ["ERROR", "WARN", "error", "warn"]}},
        ]
        query["bool"]["minimum_should_match"] = 1
    return {
        "size": args.size,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "track_total_hits": True,
        "query": query,
        "_source": SAFE_FIELDS,
    }, start, end


def mask(text):
    return SECRET_RE.sub(lambda m: m.group(1) + "***", text)


def fmt_hit(src):
    pj = src.get("parsed_json", {}) or {}
    ts = src.get("@timestamp", "")
    try:
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ALMATY).strftime("%d.%m %H:%M:%S")
    except ValueError:
        pass
    msg = " ".join(str(pj.get("message", "")).split())
    if msg == "Request info":
        msg = ""
    parts = [
        ts,
        str(pj.get("level", "")),
        str(pj.get("responseStatusCode", "")),
        f'{pj.get("requestHttpMethod", "")} {pj.get("requestMapping") or pj.get("requestUri") or ""}'.strip(),
        f'user={pj.get("username")}' if pj.get("username") else "",
        f'{pj.get("duration")}ms' if pj.get("duration") is not None else "",
        f'req={pj.get("requestId")}' if pj.get("requestId") else "",
        mask(msg[:300]),
    ]
    return " | ".join(p for p in parts if p)


def main():
    p = argparse.ArgumentParser(description="Бэкенд логтарын іздеу (тек оқу)")
    p.add_argument("--check", action="store_true", help="Kibana қолжетімді ме")
    p.add_argument("--request-id")
    p.add_argument("--user", help="username / почта")
    p.add_argument("--mapping", help='endpoint үлгісі, мысалы "/v1/unts/{id}/start"')
    p.add_argument("--text", help="message ішіндегі фраза")
    p.add_argument("--at", help='Алматы уақыты "YYYY-MM-DD HH:MM"')
    p.add_argument("--minutes", type=int, default=15, help="--at айналасындағы терезе (±мин)")
    p.add_argument("--since", help="соңғы кезең: 30m, 2h, 3d (әдепкі 24h, request-id үшін 7d)")
    p.add_argument("--errors", action="store_true", help="тек 4xx/5xx және ERROR/WARN")
    p.add_argument("--count-users", action="store_true", help="қанша бөлек пайдаланушы")
    p.add_argument("--size", type=int, default=30)
    args = p.parse_args()

    if args.check:
        st = request("GET", "/api/status")
        print(f'OK: {st.get("name")} {st.get("version", {}).get("number")}')
        return
    if not (args.request_id or args.user or args.mapping or args.text):
        die("Кемінде біреуі керек: --request-id, --user, --mapping немесе --text")
    if args.count_users:
        args.size = max(args.size, 500)

    body, start, end = build_query(args)
    path = "/api/console/proxy?" + urllib.parse.urlencode({"path": f"{INDEX}/_search", "method": "POST"})
    res = request("POST", path, body)
    hits = res.get("hits", {}).get("hits", [])
    total = res.get("hits", {}).get("total", {}).get("value", len(hits))

    if args.count_users:
        # Ауқымды бағалау: тек сандар, басқа пайдаланушылардың почталары шығарылмайды.
        users = {(h.get("_source", {}).get("parsed_json") or {}).get("username") for h in hits}
        users -= {None, "", "anonymousUser"}
        statuses = {}
        for h in hits:
            code = (h.get("_source", {}).get("parsed_json") or {}).get("responseStatusCode")
            if code is not None:
                statuses[code] = statuses.get(code, 0) + 1
        print(f"Кезең (Алматы): {start.astimezone(ALMATY):%d.%m %H:%M} — {end.astimezone(ALMATY):%d.%m %H:%M}; "
              f"жазба: {total}")
        print(f"Бөлек пайдаланушылар (алғашқы {len(hits)} жазба бойынша): {len(users)}")
        print("Статустар: " + ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items())))
        return

    print(f"Кезең (Алматы): {start.astimezone(ALMATY):%d.%m %H:%M} — {end.astimezone(ALMATY):%d.%m %H:%M}; "
          f"табылды: {total}, көрсетілді: {len(hits)}")
    for h in hits:
        print(fmt_hit(h.get("_source", {})))


if __name__ == "__main__":
    main()
