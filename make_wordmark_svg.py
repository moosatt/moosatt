"""3D ASCII wordmark: the word extruded into a slab, rasterized to characters and
rocked on its vertical axis as a pre-rendered SMIL flipbook (no JavaScript).

Usage:
  python scripts/make_wordmark_svg.py                 -> wordmark.svg (animated)
  WORDMARK_FRAME=0 STATIC=1 OUT=preview.svg python scripts/make_wordmark_svg.py   (one frozen frame)

Why a flipbook: an SVG shown through <img> in a README cannot run scripts, but it
does run SMIL. So every frame is rendered ahead of time and a discrete opacity
animation cuts between them.

Pipeline: build_shell() -> project() -> fit() -> rasterize() -> emit()
"""
import html
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TEXT = os.environ.get("WORDMARK_TEXT", "MOOSA")
FONT_CANDIDATES = [
    os.environ.get("WORDMARK_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
FONT_FACE = os.environ.get("WORDMARK_FONT_FACE", "Menlo,Consolas,'DejaVu Sans Mono',monospace")
OUT = os.environ.get("OUT", "wordmark.svg")
STATIC = os.environ.get("STATIC") == "1"
ONE_FRAME = int(os.environ["WORDMARK_FRAME"]) if "WORDMARK_FRAME" in os.environ else None

W = 460                  # panel width in px: shown 1:1 so glyphs stay crisp
CHAR_W, LINE_H, FS = 5.4, 9.0, 9
COLS = int(os.environ.get("WORDMARK_COLS", "78"))
ROW_MARGIN = int(os.environ.get("WORDMARK_ROW_MARGIN", "5"))
TITLE_H = 22
STRETCH = float(os.environ.get("WORDMARK_STRETCH", "2.4"))   # make the letters taller than the font's own proportions
PANEL_H = int(os.environ.get("WORDMARK_HEIGHT", "0"))         # 0 = hug the art; else match a neighbouring panel exactly

N_FRAMES = 20
PERIOD = 4.0             # seconds per rock cycle
SWING_DEG = float(os.environ.get("WORDMARK_SWING", "13"))
TILT_DEG = float(os.environ.get("WORDMARK_TILT", "4"))
CAM_DIST = 6.0           # in units of letter height: far enough to stay near-isometric
DEPTH_FRAC = 0.30        # extrusion depth as a fraction of letter height
TRACKING = float(os.environ.get("WORDMARK_TRACKING", "0.12"))   # extra gap between letters, fraction of height
LIGHT = np.array([-0.15, -0.45, -1.0])   # toward the light; keyed near the view axis so faces stay dense
LIGHT = LIGHT / np.linalg.norm(LIGHT)
RAMP = " .`:-=+*csS#%@"                   # sparse/dim -> dense/bright
FG, BG, CURSOR = "#e6edf3", "#0d1117", "#58a6ff"


def find_font():
    for p in FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    raise SystemExit("No bold TTF found; set WORDMARK_FONT=/path/to/font.ttf")


def build_shell():
    """Surface point cloud (points + outward normals) of the extruded word."""
    big = 220
    font = ImageFont.truetype(find_font(), big)
    track = int(TRACKING * big)
    widths = [font.getlength(ch) for ch in TEXT]
    canvas = Image.new("L", (int(sum(widths) + track * len(TEXT) + 80), int(big * 1.6)), 0)
    d = ImageDraw.Draw(canvas)
    x = 40
    for ch, wch in zip(TEXT, widths):
        d.text((x, 20), ch, font=font, fill=255)
        x += wch + track
    canvas = canvas.crop(canvas.getbbox())

    mask_w = COLS * 3                                 # ~3 surface samples per output column
    mask_h = max(8, round(canvas.height * mask_w / canvas.width * STRETCH))
    m = np.asarray(canvas.resize((mask_w, mask_h), Image.LANCZOS)) > 110

    H, Wm = m.shape
    depth = DEPTH_FRAC * H / STRETCH
    ys, xs = np.nonzero(m)
    cx, cy = Wm / 2, H / 2
    # Front cap sits proud of the walls (z = -0.6) so it wins every z-buffer tie.
    front = np.stack([xs - cx, ys - cy, np.full(xs.shape, -0.6)], 1)
    front_n = np.tile([0.0, 0.0, -1.0], (len(xs), 1))

    pad = np.pad(m, 1)
    up, down = ~pad[:-2, 1:-1], ~pad[2:, 1:-1]
    left, right = ~pad[1:-1, :-2], ~pad[1:-1, 2:]
    edge = m & (up | down | left | right)
    ey, ex = np.nonzero(edge)
    nx = right[ey, ex].astype(float) - left[ey, ex].astype(float)
    ny = down[ey, ex].astype(float) - up[ey, ex].astype(float)
    nl = np.hypot(nx, ny)
    keep = nl > 0
    ex, ey, nx, ny, nl = ex[keep], ey[keep], nx[keep], ny[keep], nl[keep]
    zs = np.arange(0.0, depth, 0.5)
    wall = np.stack([np.repeat(ex - cx, len(zs)), np.repeat(ey - cy, len(zs)), np.tile(zs, len(ex))], 1)
    wall_n = np.stack([np.repeat(nx / nl, len(zs)), np.repeat(ny / nl, len(zs)), np.zeros(len(ex) * len(zs))], 1)
    return np.vstack([front, wall]), np.vstack([front_n, wall_n]), H


def project(P, N, H, yaw_deg):
    yaw, tilt = math.radians(yaw_deg), math.radians(TILT_DEG)
    Ry = np.array([[math.cos(yaw), 0, math.sin(yaw)], [0, 1, 0], [-math.sin(yaw), 0, math.cos(yaw)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]])
    R = Rx @ Ry
    p, n = P @ R.T, N @ R.T
    vis = n[:, 2] < 0                                    # back-face cull: keep faces turned to the camera
    p, n = p[vis], n[vis]
    cam = CAM_DIST * H
    f = cam / (cam + p[:, 2])
    sx, sy = p[:, 0] * f, p[:, 1] * f
    lam = np.clip(n @ LIGHT, 0, 1)
    fog = 1 - 0.30 * (p[:, 2] - p[:, 2].min()) / max(np.ptp(p[:, 2]), 1e-6)
    bright = (0.10 + 0.90 * lam) * fog
    return sx, sy, p[:, 2], bright


def render_frames():
    P, N, H = build_shell()
    yaws = [SWING_DEG * math.sin(2 * math.pi * i / N_FRAMES) for i in range(N_FRAMES)]
    proj = [project(P, N, H, y) for y in yaws]
    # fit(): one scale + offset that boxes every frame, so nothing jitters or clips.
    x0 = min(p[0].min() for p in proj); x1 = max(p[0].max() for p in proj)
    y0 = min(p[1].min() for p in proj); y1 = max(p[1].max() for p in proj)
    sc = (COLS - 1) / (x1 - x0)
    art_rows = int(math.ceil((y1 - y0) * sc * CHAR_W / LINE_H)) + 1
    margin = ROW_MARGIN
    if PANEL_H:
        margin = max(0, (int((PANEL_H - TITLE_H - 24) / LINE_H) - art_rows) // 2)
    rows = art_rows + 2 * margin
    frames = []
    for sx, sy, z, b in proj:
        col = np.clip(((sx - x0) * sc).round().astype(int), 0, COLS - 1)
        row = np.clip(((sy - y0) * sc * CHAR_W / LINE_H).round().astype(int) + margin, 0, rows - 1)
        idx = np.clip((b * (len(RAMP) - 1)).round().astype(int), 1, len(RAMP) - 1)
        grid = np.zeros((rows, COLS), int)
        order = np.argsort(-z)                          # far -> near: nearest wins the overwrite
        grid[row[order], col[order]] = idx[order]
        frames.append(["".join(RAMP[v] for v in r).rstrip() for r in grid])
    return frames, rows


def emit(frames, rows):
    pad_x = (W - COLS * CHAR_W) / 2
    top = TITLE_H + 10 + ROW_MARGIN * 0
    height = PANEL_H or int(top + rows * LINE_H + 14)
    t_wipe, wipe_dur = 0.3, 1.2
    t_start = t_wipe + wipe_dur + 0.1
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}">',
        f'<rect width="100%" height="100%" rx="10" fill="{BG}" stroke="#30363d"/>',
        '<circle cx="18" cy="14" r="4.5" fill="#ff5f56"/><circle cx="34" cy="14" r="4.5" fill="#ffbd2e"/>'
        '<circle cx="50" cy="14" r="4.5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="18" text-anchor="middle" font-family="{FONT_FACE}" font-size="10" fill="#8b949e">'
        "moosa@github: ~$ ./wordmark.sh --3d</text>",
    ]
    show = [ONE_FRAME] if ONE_FRAME is not None else range(len(frames))
    if STATIC:
        o.append(f'<g font-family="{FONT_FACE}" font-size="{FS}" font-weight="bold" fill="{FG}" xml:space="preserve">')
        o.append(group(frames[show[0]], pad_x, top, ""))
        o.append("</g></svg>")
        return "\n".join(o)

    o.append(
        f'<defs><clipPath id="wipe"><rect x="0" y="{TITLE_H}" width="0" height="{height}">'
        f'<animate attributeName="width" from="0" to="{W}" begin="{t_wipe}s" dur="{wipe_dur}s" fill="freeze"/>'
        "</rect></clipPath></defs>"
    )
    o.append(f'<g clip-path="url(#wipe)" font-family="{FONT_FACE}" font-size="{FS}" font-weight="bold" fill="{FG}" xml:space="preserve">')
    # Intro pose (yaw 0 = frame 0) holds while the wipe runs, then hands over to the loop.
    o.append(group(frames[0], pad_x, top, f'<set attributeName="opacity" to="0" begin="{t_start:.2f}s" fill="freeze"/>', opacity="1"))
    n = len(frames)
    for i, fr in enumerate(frames):
        a, b = i / n, (i + 1) / n
        if i == 0:
            anim = f'values="1;0" keyTimes="0;{b:.4f}"'
        else:
            anim = f'values="0;1;0" keyTimes="0;{a:.4f};{b:.4f}"'
        o.append(group(fr, pad_x, top,
                       f'<animate attributeName="opacity" calcMode="discrete" {anim} dur="{PERIOD}s" '
                       f'begin="{t_start:.2f}s" repeatCount="indefinite"/>', opacity="0"))
    o.append("</g></svg>")
    return "\n".join(o)


def group(frame, pad_x, top, inner, opacity=None):
    attr = f' opacity="{opacity}"' if opacity is not None else ""
    g = [f"<g{attr}>{inner}"]
    for r, line in enumerate(frame):
        text = line.strip()
        if not text:
            continue
        lead = len(line) - len(line.lstrip())
        g.append(
            f'<text x="{pad_x + lead * CHAR_W:.1f}" y="{top + r * LINE_H:.1f}" '
            f'textLength="{len(text) * CHAR_W:.1f}" lengthAdjust="spacing">{html.escape(text)}</text>'
        )
    g.append("</g>")
    return "".join(g)


if __name__ == "__main__":
    frames, rows = render_frames()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(emit(frames, rows))
    print(f"wrote {OUT}: {len(frames)} frames, {rows} rows x {COLS} cols")
    if ONE_FRAME is not None or STATIC:
        print("\n".join(frames[ONE_FRAME or 0]))
