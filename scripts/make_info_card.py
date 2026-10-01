"""Hand-authored neofetch-style info card (animated SVG).

Usage: python scripts/make_info_card.py          -> info-card.svg
       STATIC=1 OUT=preview.svg python scripts/make_info_card.py   (frozen frame)

Edit the LINES list below to change what the card says.
"""
import html
import os

STATIC = os.environ.get("STATIC") == "1"
OUT = os.environ.get("OUT", "info-card.svg")
FONT = os.environ.get("FONT", "Menlo,Consolas,'DejaVu Sans Mono',monospace")

W = 340
PAD = 18
FS = 10
CHAR = 6.0
LH = 16
KEY_W = 10  # characters reserved for the key column

BG = "#0d1117"
C_TITLE = "#f0883e"
C_KEY = "#58a6ff"
C_VAL = "#c9d1d9"
C_DIM = "#8b949e"
C_OK = "#3fb950"
C_BULLET = "#d2a8ff"

# (kind, key, value)
LINES = [
    ("title", "moosa", "thalakkat"),
    ("rule", "", ""),
    ("kv", "Now", "SOC analyst track · blue team"),
    ("kv", "Focus", "Detection · triage · digital forensics"),
    ("kv", "Prev", "Pentest intern @ Knowledge Bonds"),
    ("cont", "", "IT project intern @ Abrus Networks"),
    ("kv", "Edu", "BSc (Hons) Cyber Security & Forensics"),
    ("cont", "", "First Class · Middlesex Dubai · 3.95/4.0"),
    ("kv", "Certs", "Security+ · BTJA · eJPTv2 · Fortinet FCA"),
    ("cont", "", "ICCA · Google Cybersecurity"),
    ("kv", "Detect", "Suricata · OPNsense · Splunk · ELK"),
    ("cont", "", "Wireshark · MITRE ATT&CK"),
    ("kv", "Forensics", "Volatility · Autopsy · FTK Imager · YARA"),
    ("kv", "Code", "Python · Bash · PowerShell · SQL"),
    ("blank", "", ""),
    ("section", "Highlights", ""),
    ("bullet", "", "IDS alert triage at 95.7% (RF + SHAP)"),
    ("bullet", "", "3 forensic cases: memory, email, disk"),
    ("bullet", "", "15 findings across 3 black-box pentests"),
    ("bullet", "", "4th of 37 UAE teams · EC-Council CTF"),
    ("blank", "", ""),
    ("palette", "", ""),
]

PALETTE = ["#161b22", "#f85149", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#c9d1d9"]


def esc(s):
    return html.escape(s, quote=False)


def build():
    top = 46
    height = top + len(LINES) * LH + 16
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}">',
        f'<rect width="100%" height="100%" rx="10" fill="{BG}" stroke="#30363d"/>',
        '<circle cx="18" cy="14" r="4.5" fill="#ff5f56"/><circle cx="34" cy="14" r="4.5" fill="#ffbd2e"/>'
        '<circle cx="50" cy="14" r="4.5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="18" text-anchor="middle" font-family="{FONT}" font-size="10" fill="{C_DIM}">'
        "moosa@github: ~/neofetch</text>",
        f'<g font-family="{FONT}" font-size="{FS}">',
    ]
    kx = PAD
    vx = PAD + KEY_W * CHAR
    for i, (kind, key, val) in enumerate(LINES):
        y = top + i * LH
        begin = 0.3 + i * 0.11
        if STATIC:
            open_g = "<g>"
        else:
            open_g = (
                '<g opacity="0">'
                f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="0.35s" fill="freeze"/>'
                f'<animateTransform attributeName="transform" type="translate" from="-8 0" to="0 0" '
                f'begin="{begin:.2f}s" dur="0.35s" fill="freeze"/>'
            )
        body = ""
        if kind == "title":
            body = (
                f'<text x="{kx}" y="{y}" fill="{C_TITLE}" font-weight="bold">{esc(key)}</text>'
                f'<text x="{kx + len(key) * CHAR:.1f}" y="{y}" fill="{C_DIM}">@</text>'
                f'<text x="{kx + (len(key) + 1) * CHAR:.1f}" y="{y}" fill="{C_TITLE}" font-weight="bold">{esc(val)}</text>'
            )
        elif kind == "rule":
            body = f'<text x="{kx}" y="{y}" fill="{C_DIM}">{"-" * 15}</text>'
        elif kind == "kv":
            body = (
                f'<text x="{kx}" y="{y}" fill="{C_KEY}" font-weight="bold">{esc(key)}</text>'
                f'<text x="{vx:.1f}" y="{y}" fill="{C_VAL}">{esc(val)}</text>'
            )
        elif kind == "cont":
            body = f'<text x="{vx:.1f}" y="{y}" fill="{C_VAL}">{esc(val)}</text>'
        elif kind == "section":
            body = f'<text x="{kx}" y="{y}" fill="{C_OK}" font-weight="bold">{esc(key)}</text>'
        elif kind == "bullet":
            body = (
                f'<text x="{kx}" y="{y}" fill="{C_BULLET}">▸</text>'
                f'<text x="{kx + 2 * CHAR:.1f}" y="{y}" fill="{C_VAL}">{esc(val)}</text>'
            )
        elif kind == "palette":
            body = "".join(
                f'<rect x="{kx + j * 26}" y="{y - 11}" width="24" height="12" rx="2" fill="{c}"/>'
                for j, c in enumerate(PALETTE)
            )
        out.append(open_g + body + "</g>")
    out.append("</g></svg>")
    return "\n".join(out)


if __name__ == "__main__":
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"wrote {OUT}")
