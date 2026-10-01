"""Convert the prepped portrait into a self-typing, monochrome ASCII SVG.

Usage: python scripts/make_ascii_svg.py   (reads source-prepped.png + source-mask.png)
Writes: moosa-ascii.svg
"""
import html
import os

import numpy as np
from PIL import Image

# STATIC=1 emits the finished frame with no animation (for local previews).
STATIC = os.environ.get("STATIC") == "1"
OUT = os.environ.get("OUT", "moosa-ascii.svg")
# INVERT=1 (default): dark = dense glyphs. Best for whole-frame photos on a dark
# terminal. INVERT=0: bright = dense, best for a cut-out subject.
INVERT = os.environ.get("INVERT", "1") == "1"
# Font stack for GitHub viewers (Menlo on macOS, Consolas on Windows, DejaVu on Linux).
FONT = os.environ.get("FONT", "Menlo,Consolas,'DejaVu Sans Mono',monospace")

COLS = int(os.environ.get("COLS", "170"))
CHAR_W = 3.6          # px per glyph at font-size 6 (monospace ~0.6em)
LINE_H = 6.0
FONT_SIZE = 6
BG_TONE = os.environ.get("BG_TONE", "pos")           # "neg" or "pos", see build_rows()
FLOOR = float(os.environ.get("FLOOR", "0.23"))       # tones below this print as blank (raise it for dark photos)
BG_DIM = float(os.environ.get("BG_DIM", "0.55"))   # background strength vs subject (1 = no dimming)
PAD = 14
FG = "#e6edf3"
BG = "#0d1117"
CURSOR = "#58a6ff"

# sparse -> dense. On a dark background, dense = bright.
RAMP = " .,:;-~=+*xX#%8@"


def build_rows():
    gray = Image.open("source-prepped.png").convert("L")
    mask = Image.open("source-mask.png").convert("L")
    w, h = gray.size
    rows = int(COLS * (h / w) * (CHAR_W / LINE_H))
    # INTER_AREA-style averaging keeps fine detail when shrinking a lot.
    gray = np.asarray(gray.resize((COLS, rows), Image.BOX), dtype=float) / 255.0
    mask = np.asarray(mask.resize((COLS, rows), Image.BOX), dtype=float) / 255.0

    # Soft subject mask (from prep_photo.py --full): the background is dimmed so
    # the person pops out instead of competing with the wall and panel.
    subj = np.ones_like(mask)
    if os.path.exists("source-subject.png"):
        s = Image.open("source-subject.png").convert("L").resize((COLS, rows), Image.BOX)
        subj = np.asarray(s, dtype=float) / 255.0

    # Tone map. With a subject mask (prep_photo.py --full) the person is printed
    # "lit" (bright skin -> dense glyphs, so a face reads as a face) while the
    # background is inverted and dimmed (dark shapes -> faint glyphs), so the
    # whole frame is kept but the subject leads. Without a mask, INVERT picks
    # one mapping for the whole picture.
    has_subject = os.path.exists("source-subject.png")
    ref = gray[(mask > 0.5) & (subj > 0.5)] if has_subject and (subj > 0.5).any() else gray[mask > 0.5]
    lo, hi = np.percentile(ref, [2, 99])
    norm = np.clip((gray - lo) / max(hi - lo, 1e-6), 0, 1)
    pos = norm ** 1.3                      # bright -> dense
    neg = (1 - norm) ** 0.9                # dark -> dense
    if has_subject:
        weight = BG_DIM + (1 - BG_DIM) * subj
        # Background tone: "neg" prints dark shapes (good for a light backdrop),
        # "pos" prints bright shapes (good for a dark backdrop: it stays blank).
        bg_tone = pos if BG_TONE == "pos" else neg
        tone = subj * pos + (1 - subj) * bg_tone
    else:
        weight = np.ones_like(norm)
        tone = neg if INVERT else pos

    # Edge boost so eyes, brows, nose and lips stay legible at low resolution.
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
    gy[1:-1, :] = gray[2:, :] - gray[:-2, :]
    edge = np.hypot(gx, gy)
    edge = np.clip(edge / (np.percentile(edge[mask > 0.5], 97) + 1e-6), 0, 1)
    lum = np.clip(tone * 0.85 + edge * 0.30, 0, 1) * weight
    lum = np.clip((lum - FLOOR) / (1 - FLOOR), 0, 1)   # noise floor: faint tones print as blank, no haze or streaks

    idx = np.clip((lum * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)

    out = []
    for y in range(rows):
        line = "".join(RAMP[idx[y, x]] if mask[y, x] > 0.5 else " " for x in range(COLS))
        out.append(line.rstrip())
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def make_svg(rows):
    width = COLS * CHAR_W + PAD * 2
    height = len(rows) * LINE_H + PAD * 2 + 22 + 26
    top = PAD + 22
    per_row = 0.03           # stagger between rows
    wipe = 0.55              # duration of each row's left-to-right wipe

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">',
        f'<rect width="100%" height="100%" rx="10" fill="{BG}" stroke="#30363d"/>',
        '<circle cx="18" cy="14" r="4.5" fill="#ff5f56"/>'
        '<circle cx="34" cy="14" r="4.5" fill="#ffbd2e"/>'
        '<circle cx="50" cy="14" r="4.5" fill="#27c93f"/>',
        f'<text x="{width/2:.0f}" y="18" text-anchor="middle" font-family="{FONT}" '
        f'font-size="10" fill="#8b949e">moosa@github: ~$ ./portrait.st</text>',
        "<defs>",
    ]
    for i in range(len(rows)):
        y = top + i * LINE_H - FONT_SIZE
        t0 = 0.3 + i * per_row
        if STATIC:
            parts.append(
                f'<clipPath id="c{i}"><rect x="{PAD}" y="{y:.1f}" width="{COLS * CHAR_W:.1f}" height="{LINE_H + 1}"/></clipPath>'
            )
            continue
        parts.append(
            f'<clipPath id="c{i}"><rect x="{PAD}" y="{y:.1f}" width="0" height="{LINE_H + 1}">'
            f'<animate attributeName="width" from="0" to="{COLS * CHAR_W:.1f}" begin="{t0:.2f}s" '
            f'dur="{wipe}s" fill="freeze"/></rect></clipPath>'
        )
    parts.append("</defs>")
    parts.append(
        f'<g font-family="{FONT}" font-size="{FONT_SIZE}" font-weight="bold" fill="{FG}" '
        'xml:space="preserve" style="white-space:pre">'
    )
    for i, line in enumerate(rows):
        y = top + i * LINE_H
        text = line.strip()
        if not text:
            continue
        lead = len(line) - len(line.lstrip())
        # Position each row by its own leading offset and give it its own
        # textLength, so short rows are never stretched to the full width.
        parts.append(
            f'<text x="{PAD + lead * CHAR_W:.1f}" y="{y:.1f}" clip-path="url(#c{i})" '
            f'textLength="{len(text) * CHAR_W:.1f}" lengthAdjust="spacing">{html.escape(text)}</text>'
        )
    parts.append("</g>")

    # Cursor block that rides each row's wipe edge, one row at a time.
    for i in range(0 if STATIC else len(rows)):
        y = top + i * LINE_H - FONT_SIZE
        t0 = 0.3 + i * per_row
        parts.append(
            f'<rect x="{PAD}" y="{y:.1f}" width="{CHAR_W:.1f}" height="{LINE_H:.1f}" fill="{CURSOR}" opacity="0">'
            f'<animate attributeName="x" from="{PAD}" to="{PAD + COLS * CHAR_W:.1f}" begin="{t0:.2f}s" dur="{wipe}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0.9;0.9;0" keyTimes="0;0.95;1" begin="{t0:.2f}s" dur="{wipe}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.9" begin="{t0:.2f}s"/>'
            "</rect>"
        )
    # Typed shell prompt along the bottom edge, after the portrait finishes printing.
    cw = 4.8                                   # glyph width at font-size 8
    prompt, name = "moosa@github:~$ whoami  ", "Moosa Thalakkat"
    py = top + len(rows) * LINE_H + 20
    tl = (len(prompt) + len(name)) * cw
    t_prompt = 0.3 + len(rows) * per_row + wipe + 0.2
    typed = 1.2
    if STATIC:
        parts.append(f'<clipPath id="pc"><rect x="{PAD}" y="{py - 9}" width="{tl}" height="12"/></clipPath>')
    else:
        parts.append(
            f'<clipPath id="pc"><rect x="{PAD}" y="{py - 9}" width="0" height="12">'
            f'<animate attributeName="width" from="0" to="{tl}" begin="{t_prompt:.2f}s" dur="{typed}s" fill="freeze"/>'
            "</rect></clipPath>"
        )
    parts.append(
        f'<g font-family="{FONT}" font-size="8" clip-path="url(#pc)" xml:space="preserve">'
        f'<text x="{PAD}" y="{py}" fill="#3fb950" textLength="{len(prompt) * cw}" lengthAdjust="spacing">{html.escape(prompt)}</text>'
        f'<text x="{PAD + len(prompt) * cw}" y="{py}" fill="{FG}" textLength="{len(name) * cw}" lengthAdjust="spacing">{html.escape(name)}</text>'
        "</g>"
    )
    cur_x = PAD + tl + 2
    if STATIC:
        parts.append(f'<rect x="{cur_x}" y="{py - 8}" width="{cw}" height="9" fill="{CURSOR}"/>')
    else:
        t_cur = t_prompt + typed
        parts.append(
            f'<rect x="{cur_x}" y="{py - 8}" width="{cw}" height="9" fill="{CURSOR}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{t_cur:.2f}s"/>'
            f'<animate attributeName="opacity" calcMode="discrete" values="1;0" dur="1s" begin="{t_cur:.2f}s" repeatCount="indefinite"/>'
            "</rect>"
        )
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    rows = build_rows()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(make_svg(rows))
    print(f"wrote {OUT} ({len(rows)} rows x {COLS} cols)")
