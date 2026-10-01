"""Render data/contributions.json as an animated 53-week contribution heatmap SVG.

Usage: python scripts/render_heatmap_svg.py              -> contrib-heatmap.svg
       STATIC=1 OUT=preview.svg python scripts/render_heatmap_svg.py
       SAMPLE=1 ...   render synthetic activity (preview only; never commit this)
"""
import json
import os
import random
from datetime import date, datetime, timedelta

STATIC = os.environ.get("STATIC") == "1"
SAMPLE = os.environ.get("SAMPLE") == "1"
OUT = os.environ.get("OUT", "contrib-heatmap.svg")
FONT = os.environ.get("FONT", "Menlo,Consolas,'DejaVu Sans Mono',monospace")

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
W = 860
PAD = 20
LEFT = 34
TOP = 46
WEEKS = 53


def load():
    with open("data/contributions.json") as f:
        data = json.load(f)
    if SAMPLE:
        rnd = random.Random(7)
        for d in data["days"]:
            dt = date.fromisoformat(d["date"])
            busy = 0.75 if dt.weekday() < 5 else 0.3
            n = int(rnd.expovariate(0.35)) if rnd.random() < busy else 0
            d["count"] = n
            d["level"] = 0 if n == 0 else 1 if n < 3 else 2 if n < 6 else 3 if n < 10 else 4
        # recompute stats the same way the fetch script does
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location("fc", os.path.join(os.path.dirname(__file__), "fetch_contributions.py"))
        fc = importlib.util.module_from_spec(spec)
        sys.modules["fc"] = fc
        spec.loader.exec_module(fc)
        data.update(fc.stats(data["days"]))
    return data


def render(data):
    days = data["days"]
    first = date.fromisoformat(days[0]["date"])
    start = first - timedelta(days=(first.weekday() + 1) % 7)  # Sunday on/before first day
    cell = (W - 2 * PAD - LEFT) / WEEKS
    box = cell - 3
    mx = max((d["count"] for d in days), default=0)

    height = TOP + 7 * cell + 46
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height:.0f}" viewBox="0 0 {W} {height:.0f}">',
        '<style>',
        f'text{{font-family:{FONT};}}',
    ]
    if not STATIC:
        o.append(
            ".d{opacity:0;animation:in .45s ease-out forwards}"
            "@keyframes in{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}"
        )
    o.append("</style>")
    o.append(f'<rect width="100%" height="100%" rx="10" fill="#0d1117" stroke="#30363d"/>')

    # month labels
    last_label_week = -10
    last_month = None
    for w in range(WEEKS):
        wk_start = start + timedelta(weeks=w)
        # label the week that contains the 1st-7th of a new month
        m = (wk_start + timedelta(days=6)).month
        if m != last_month and (wk_start + timedelta(days=6)).day <= 7 or (w == 0):
            if w - last_label_week >= 3:
                o.append(
                    f'<text x="{PAD + LEFT + w * cell:.1f}" y="{TOP - 12}" font-size="10" fill="#8b949e">'
                    f'{(wk_start + timedelta(days=6)).strftime("%b")}</text>'
                )
                last_label_week = w
        last_month = m

    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o.append(
            f'<text x="{PAD}" y="{TOP + row * cell + box - 2:.1f}" font-size="10" fill="#8b949e">{label}</text>'
        )

    for d in days:
        dt = date.fromisoformat(d["date"])
        w = (dt - start).days // 7
        dow = (dt.weekday() + 1) % 7
        lvl = d["level"]
        if lvl == 4 and mx and d["count"] >= 0.75 * mx:
            lvl = 5
        x = PAD + LEFT + w * cell
        y = TOP + dow * cell
        tip = f'{d["count"]} contribution{"s" if d["count"] != 1 else ""} on {d["date"]}'
        attrs = f'x="{x:.1f}" y="{y:.1f}" width="{box:.1f}" height="{box:.1f}" rx="3" fill="{PALETTE[lvl]}"'
        if STATIC:
            o.append(f"<rect {attrs}><title>{tip}</title></rect>")
        else:
            delay = (w + dow) * 0.012
            o.append(f'<rect class="d" style="animation-delay:{delay:.3f}s" {attrs}><title>{tip}</title></rect>')

    # legend + stats
    fy = TOP + 7 * cell + 26
    lx = W - PAD - 6 * (box + 3) - 80
    o.append(f'<text x="{lx:.0f}" y="{fy + 9}" font-size="10" fill="#8b949e" text-anchor="end">Less</text>')
    for i, c in enumerate(PALETTE):
        o.append(f'<rect x="{lx + 8 + i * (box + 3):.1f}" y="{fy}" width="{box:.1f}" height="{box:.1f}" rx="3" fill="{c}"/>')
    o.append(f'<text x="{lx + 14 + 6 * (box + 3):.1f}" y="{fy + 9}" font-size="10" fill="#8b949e">More</text>')

    total = data["total"]
    best = data["best_day"]
    summary = f'{total:,} contribution{"s" if total != 1 else ""} in the last year'
    o.append(f'<text x="{PAD + LEFT}" y="{fy + 10}" font-size="12" fill="#c9d1d9" font-weight="bold">{summary}</text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(load()))
    print(f"wrote {OUT}")
