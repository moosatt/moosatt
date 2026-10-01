"""Generate flat 'for-the-badge' style SVG badges locally (no shields.io dependency).

Usage: python scripts/make_badges.py     -> badges/*.svg
Edit BADGES below to change the text or colours. Widths are computed from the
text length and fixed with textLength, so they render the same in any browser.
"""
import html
import os

FONT = "Verdana,'DejaVu Sans',Geneva,sans-serif"
H = 28
CW = 7.4        # px per character at font-size 10.5 incl. letter-spacing
PADX = 14
LABEL_BG = "#555555"

# file, label, value, value background, value text colour, border
BADGES = [
    ("linkedin", "LINKEDIN", "MOOSA-THALAKKAT", "#0a66c2", "#ffffff", None),
    ("github", "GITHUB", "MOOSATT", "#161b22", "#ffffff", "#30363d"),
    ("certs", "CERTS", "SECURITY+ · BTJA · EJPTV2", "#8957e5", "#ffffff", None),
    ("open-to", "OPEN TO", "SOC ANALYST ROLES", "#22d3ee", "#0d1117", None),
]


def badge(label, value, vbg, vfg, border):
    lw = len(label) * CW + 2 * PADX
    vw = len(value) * CW + 2 * PADX
    w = lw + vw
    stroke = f' stroke="{border}"' if border else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{H}" viewBox="0 0 {w:.0f} {H}" role="img" '
        f'aria-label="{html.escape(label)}: {html.escape(value)}">'
        f'<clipPath id="r"><rect width="{w:.0f}" height="{H}" rx="3"/></clipPath>'
        f'<g clip-path="url(#r)"><rect width="{lw:.0f}" height="{H}" fill="{LABEL_BG}"/>'
        f'<rect x="{lw:.0f}" width="{vw:.0f}" height="{H}" fill="{vbg}"/></g>'
        f'<rect width="{w:.0f}" height="{H}" rx="3" fill="none"{stroke}/>'
        f'<g font-family="{FONT}" font-size="10.5" font-weight="bold" text-anchor="middle">'
        f'<text x="{lw / 2:.1f}" y="18" fill="#ffffff" textLength="{len(label) * CW:.1f}" lengthAdjust="spacing">{html.escape(label)}</text>'
        f'<text x="{lw + vw / 2:.1f}" y="18" fill="{vfg}" textLength="{len(value) * CW:.1f}" lengthAdjust="spacing">{html.escape(value)}</text>'
        "</g></svg>"
    )


if __name__ == "__main__":
    os.makedirs("badges", exist_ok=True)
    for name, label, value, vbg, vfg, border in BADGES:
        with open(f"badges/{name}.svg", "w", encoding="utf-8") as f:
            f.write(badge(label, value, vbg, vfg, border))
        print(f"wrote badges/{name}.svg")
