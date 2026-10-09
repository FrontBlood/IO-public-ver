"""Generate reproducible activity and retention metrics from the bot SQLite data.

The primary activity fact table is levels.db/daily_xp_log.  One row means that a
user earned XP in one channel (text/voice/stream) on one UTC calendar day.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def _iso_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _days(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _pct(numerator: int | float, denominator: int | float) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _period(events: list[dict], start: date, end: date) -> dict:
    rows = [r for r in events if start <= r["date"] <= end]
    users = {r["user_id"] for r in rows}
    daily_users: dict[date, set[str]] = {d: set() for d in _days(start, end)}
    channel_users: dict[str, set[str]] = defaultdict(set)
    channel_xp: dict[str, int] = defaultdict(int)
    for row in rows:
        daily_users[row["date"]].add(row["user_id"])
        channel_users[row["xp_type"]].add(row["user_id"])
        channel_xp[row["xp_type"]] += row["amount"]
    dau_values = [len(daily_users[d]) for d in _days(start, end)]
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "users": users,
        "wau": len(users),
        "avg_dau": round(sum(dau_values) / len(dau_values), 1),
        "peak_dau": max(dau_values),
        "stickiness": _pct(sum(dau_values) / len(dau_values), len(users)),
        "total_xp": sum(r["amount"] for r in rows),
        "channel_users": {k: len(v) for k, v in sorted(channel_users.items())},
        "channel_xp": dict(sorted(channel_xp.items())),
        "daily": [
            {
                "date": d.isoformat(),
                "dau": len(daily_users[d]),
                "xp": sum(r["amount"] for r in rows if r["date"] == d),
            }
            for d in _days(start, end)
        ],
    }


def build_report(levels_db: Path, end: date | None = None, auto_complete_day: bool = True) -> dict:
    conn = _connect_readonly(levels_db)
    try:
        raw = conn.execute(
            "SELECT user_id, xp_type, date, amount FROM daily_xp_log ORDER BY date, user_id"
        ).fetchall()
        registered_users = conn.execute("SELECT COUNT(*) FROM user_xp").fetchone()[0]
    finally:
        conn.close()

    if not raw:
        raise RuntimeError("daily_xp_log is empty")
    events = [
        {"user_id": str(u), "xp_type": str(t), "date": _iso_day(d), "amount": int(a)}
        for u, t, d, a in raw
    ]
    first_day, latest_day = events[0]["date"], events[-1]["date"]
    daily_counts: dict[date, set[str]] = defaultdict(set)
    for row in events:
        daily_counts[row["date"]].add(row["user_id"])

    excluded_partial_day = None
    if end is None:
        end = latest_day
        previous_counts = [len(daily_counts[latest_day - timedelta(days=i)]) for i in range(1, 8)]
        baseline = statistics.median(previous_counts) if previous_counts else 0
        if auto_complete_day and baseline and len(daily_counts[latest_day]) < baseline * 0.7:
            excluded_partial_day = latest_day.isoformat()
            end -= timedelta(days=1)
    if end > latest_day:
        raise ValueError(f"end date {end} is after latest activity date {latest_day}")

    current_start = end - timedelta(days=6)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    current = _period(events, current_start, end)
    previous = _period(events, previous_start, previous_end)
    current_users, previous_users = current.pop("users"), previous.pop("users")
    first_seen: dict[str, date] = {}
    for row in events:
        first_seen.setdefault(row["user_id"], row["date"])
    new_users = {u for u in current_users if current_start <= first_seen[u] <= end}
    retained = current_users & previous_users
    resurrected = current_users - previous_users - new_users
    churned = previous_users - current_users

    comparison = {}
    for key in ("wau", "avg_dau", "total_xp"):
        comparison[key] = {
            "current": current[key],
            "previous": previous[key],
            "change_rate": None if not previous[key] else round(current[key] / previous[key] - 1, 4),
        }

    # Activity-based weekly cohorts. Cohort week starts on Monday.
    def week_start(d: date) -> date:
        return d - timedelta(days=d.weekday())

    cohorts: dict[date, set[str]] = defaultdict(set)
    active_by_week: dict[date, set[str]] = defaultdict(set)
    for user, seen in first_seen.items():
        cohorts[week_start(seen)].add(user)
    for row in events:
        active_by_week[week_start(row["date"])].add(row["user_id"])
    cohort_rows = []
    for cohort_week in sorted(cohorts)[-12:]:
        cohort = cohorts[cohort_week]
        row = {"cohort_week": cohort_week.isoformat(), "size": len(cohort)}
        for offset in range(4):
            active = active_by_week.get(cohort_week + timedelta(days=7 * offset), set())
            row[f"w{offset}"] = _pct(len(cohort & active), len(cohort))
        cohort_rows.append(row)

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(levels_db),
        "source_coverage": {"first": first_day.isoformat(), "latest": latest_day.isoformat()},
        "excluded_partial_day": excluded_partial_day,
        "registered_users": registered_users,
        "current": current,
        "previous": previous,
        "comparison": comparison,
        "retention": {
            "retained_users": len(retained),
            "week_over_week_retention": _pct(len(retained), len(previous_users)),
            "new_active_users": len(new_users),
            "resurrected_users": len(resurrected),
            "churned_users": len(churned),
        },
        "cohorts": cohort_rows,
        "definitions": {
            "active_user": "UTC日内在 daily_xp_log 至少有一条文字/语音/直播 XP 记录的用户",
            "wau": "连续7个UTC自然日内的去重活跃用户数",
            "week_over_week_retention": "上一个7日窗口用户中，本7日窗口再次活跃的比例",
            "new_active_user": "首次出现于 daily_xp_log 且首次日期落在本周期的用户",
            "resurrected_user": "本周期活跃、上周期未活跃、且不是新用户",
            "stickiness": "周期平均DAU / WAU",
        },
    }


def write_csvs(report: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("daily_activity", report["current"]["daily"]), ("cohort_retention", report["cohorts"])):
        if not rows:
            continue
        with (output_dir / f"{name}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="用户活跃与留存周报分析")
    parser.add_argument("--levels-db", type=Path, default=Path("levels.db"))
    parser.add_argument("--end", type=date.fromisoformat, help="报告结束日期 YYYY-MM-DD")
    parser.add_argument("--include-latest", action="store_true", help="不自动排除疑似未完结的最新一天")
    parser.add_argument("--json", type=Path, help="写入完整 JSON 报告")
    parser.add_argument("--csv-dir", type=Path, help="写入日活与 cohort CSV")
    args = parser.parse_args()
    report = build_report(args.levels_db, args.end, not args.include_latest)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.csv_dir:
        write_csvs(report, args.csv_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
