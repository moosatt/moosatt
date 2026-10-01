"""Fetch the public contribution calendar for a GitHub user. No token needed.

Usage: python scripts/fetch_contributions.py [username]
       python scripts/fetch_contributions.py --empty [username]   (seed a blank calendar)

GitHub serves the calendar as an HTML fragment at
https://github.com/users/<username>/contributions. We parse the day cells and
write data/contributions.json with the raw days plus derived stats.
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

USERNAME = "moosatt"
OUT = "data/contributions.json"


def fetch(username):
    r = requests.get(
        f"https://github.com/users/{username}/contributions",
        headers={"User-Agent": "Mozilla/5.0 (profile-readme-bot)"},
        timeout=30,
    )
    r.raise_for_status()
    return r.text


def parse(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    tips = {t.get("for"): t.get_text(" ", strip=True) for t in soup.find_all("tool-tip")}
    days = []
    for el in soup.select("[data-date]"):
        d = el["data-date"]
        level = int(el.get("data-level", 0))
        count = 0
        text = tips.get(el.get("id"), "")
        m = re.match(r"(\d[\d,]*)\s+contribution", text)
        if m:
            count = int(m.group(1).replace(",", ""))
        if el.has_attr("data-count"):  # older markup
            count = int(el["data-count"])
        days.append({"date": d, "count": count, "level": level})
    days.sort(key=lambda x: x["date"])
    return days


def empty_calendar(today=None):
    today = today or date.today()
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    start = sunday - timedelta(weeks=52)
    n = (today - start).days + 1
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "count": 0, "level": 0}
        for i in range(n)
    ]


def stats(days):
    total = sum(d["count"] for d in days)
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    # Current streak: walk back from the latest day; an empty *today* doesn't
    # break it, since the day isn't over yet.
    current = 0
    for i, d in enumerate(reversed(days)):
        if d["count"] > 0:
            current += 1
        elif i == 0:
            continue
        else:
            break
    best = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}
    months = {}
    for d in days:
        key = d["date"][:7]
        months[key] = months.get(key, 0) + d["count"]
    return {
        "total": total,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": months,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    username = args[0] if args else USERNAME
    if "--empty" in sys.argv:
        days = empty_calendar()
    else:
        days = parse(fetch(username))
        if not days:
            sys.exit("No contribution cells found; GitHub markup may have changed.")
    data = {
        "username": username,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
        **stats(days),
    }
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
    print(f"wrote {OUT}: {len(days)} days, {data['total']} contributions")


if __name__ == "__main__":
    main()
