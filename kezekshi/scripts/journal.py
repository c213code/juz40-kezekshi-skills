#!/usr/bin/env python3
"""Кезекші журналы: әр өңделген өтініш бір жолмен жазылады, кешке — дейли-репорт.

Журнал репода емес, кезекшінің компьютерінде: ~/.kezekshi/journal/YYYY-MM-DD.jsonl
(KEZEKSHI_JOURNAL_DIR арқылы өзгертуге болады). Жеке деректер (почта, телефон) жазылмайды.

Командалар:
  journal.py add --group "IT + Сервис" --desc "Оқушыда квиз балы қойылмай тұр" \
                 --status RESOLVED --note "Ерош шешті, балл қойылды" [--link URL] [--ticket DV-123]
  journal.py update <N> --status RESOLVED --note "..."     # бүгінгі N-жазбаны жаңарту
  journal.py list [--date YYYY-MM-DD]
  journal.py due                  # репорт уақыты келді ме (18:00-ден кейін, бүгін әлі жасалмаса)
  journal.py report [--date YYYY-MM-DD] [--duty "Аты"]   # репорт мәтіні + «жасалды» деп белгілейді
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALMATY = timezone(timedelta(hours=5))
REPORT_HOUR = int(os.environ.get("KEZEKSHI_REPORT_HOUR", "18"))
SEPARATOR = "—" * 30

STATUSES = {
    "RESOLVED": ("Решено", "✅", "Шешілді"),
    "IN_PROGRESS": ("В работе", "⚠️", "Қарап жатырмыз"),
    "PENDING": ("Пендинг", "⚠️", "Пендинг"),
    "NEXT_DAY": ("На завтра", "⚠️", "Бүгін тағы да қарап көреміз"),
    "ESCALATED": ("Передано", "⚠️", "Передано другой команде"),
}
ORDER = list(STATUSES)


def journal_dir() -> Path:
    d = Path(os.environ.get("KEZEKSHI_JOURNAL_DIR", Path.home() / ".kezekshi" / "journal"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def now():
    return datetime.now(ALMATY)


def day_file(date: str) -> Path:
    return journal_dir() / f"{date}.jsonl"


def marker_file(date: str) -> Path:
    return journal_dir() / f"{date}.reported"


def load(date: str):
    f = day_file(date)
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(date: str, entries):
    day_file(date).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")


def check_status(value):
    value = value.upper()
    if value not in STATUSES:
        sys.exit(f"status: {', '.join(STATUSES)}")
    return value


def cmd_add(a):
    date = now().strftime("%Y-%m-%d")
    entries = load(date)
    entries.append({
        "ts": now().isoformat(timespec="minutes"),
        "group": a.group,
        "desc": a.desc,
        "status": check_status(a.status),
        "note": a.note or "",
        "link": a.link or "",
        "ticket": a.ticket or "",
    })
    save(date, entries)
    print(f"Журналға қосылды: №{len(entries)} ({date})")


def cmd_update(a):
    date = now().strftime("%Y-%m-%d")
    entries = load(date)
    if not 1 <= a.n <= len(entries):
        sys.exit(f"Бүгін {len(entries)} жазба бар")
    e = entries[a.n - 1]
    if a.status:
        e["status"] = check_status(a.status)
    if a.note is not None:
        e["note"] = a.note
    if a.ticket:
        e["ticket"] = a.ticket
    save(date, entries)
    print(f"№{a.n} жаңартылды")


def cmd_list(a):
    date = a.date or now().strftime("%Y-%m-%d")
    entries = load(date)
    if not entries:
        print(f"{date}: журнал бос")
    for i, e in enumerate(entries, 1):
        print(f"{i}. [{STATUSES[e['status']][0]}] {e['group']} — {e['desc']} ({e['ts'][11:16]})")


def cmd_due(_):
    date = now().strftime("%Y-%m-%d")
    entries = load(date)
    if marker_file(date).exists():
        print("NO: бүгінгі репорт жасалған")
    elif now().hour < REPORT_HOUR:
        print(f"NO: әлі ерте ({REPORT_HOUR}:00-ге дейін)")
    elif not entries:
        print("NO: бүгін журнал бос")
    else:
        print(f"YES: {len(entries)} өтініш, репорт әлі жасалмаған")


def render(date, entries, duty):
    counts = " · ".join(f"{STATUSES[s][0]}: {sum(e['status'] == s for e in entries)}" for s in ORDER)
    head = [f"📋 Репорт за {date}"]
    if duty:
        head.append(f"Дежурный: {duty}")
    head += [f"Всего в репорте: {len(entries)}", counts]

    groups = {}
    for e in entries:
        groups.setdefault(e["group"] or "Басқа", []).append(e)
    blocks = []
    for name, items in groups.items():
        lines = [name, ""]
        for i, e in enumerate(items, 1):
            lines.append(f"{i}. {e['desc']}")
            if e.get("link"):
                lines.append(e["link"])
            _, emoji, default_note = STATUSES[e["status"]]
            ticket = f" {e['ticket']}" if e.get("ticket") else ""
            lines.append(f"Статус: {e.get('note') or default_note}{ticket}{emoji}")
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
        blocks.append("\n".join(lines))
    return "\n".join(head) + "\n\n" + f"\n\n{SEPARATOR}\n".join(blocks)


def cmd_report(a):
    date = a.date or now().strftime("%Y-%m-%d")
    entries = load(date)
    if not entries:
        sys.exit(f"{date}: журнал бос, репорт жоқ")
    print(render(date, entries, a.duty))
    marker_file(date).write_text(now().isoformat(timespec="minutes"), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="Кезекші журналы және дейли-репорт")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--group", required=True)
    s.add_argument("--desc", required=True)
    s.add_argument("--status", required=True)
    s.add_argument("--note")
    s.add_argument("--link")
    s.add_argument("--ticket")
    s.set_defaults(fn=cmd_add)
    s = sub.add_parser("update")
    s.add_argument("n", type=int)
    s.add_argument("--status")
    s.add_argument("--note")
    s.add_argument("--ticket")
    s.set_defaults(fn=cmd_update)
    s = sub.add_parser("list")
    s.add_argument("--date")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("due")
    s.set_defaults(fn=cmd_due)
    s = sub.add_parser("report")
    s.add_argument("--date")
    s.add_argument("--duty")
    s.set_defaults(fn=cmd_report)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
