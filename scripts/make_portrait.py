#!/usr/bin/env python3
"""Turn a photo into an animated, monochrome ASCII terminal portrait (ascii.svg).

Features:
  - Background removal via rembg & edge-preserving smoothing
  - Monochromatic 13-level character ramp mapping (92 columns)
  - Embedded JetBrains Mono font subset (exact 0.600 em geometry)
  - SMIL initial typing reveal with riding block cursor
  - Continuous CRT scanline luminous sweep in infinite loop
  - Bottom terminal command prompt with infinite blinking cursor
  - Native GitHub Light & Dark mode adaptation

Usage:
    python scripts/make_portrait.py assets/profile.jpg --crop 20,140,588,860 --cols 92
"""
import argparse
import base64
import os
import sys
import cv2
import numpy as np
from PIL import Image
from rembg import remove

RAMP = " .`:-=+*cs#%@"     # 13 brightness levels; leading space = blank
COLS = 92                  # column density
CLAHE_CLIP = 2.5           # adaptive contrast threshold
GAMMA = 1.0                # ramp mapping exponent
CURVE = 1.65               # power curve for shadow definition
ROW_RATIO = 0.48           # monospace cell aspect ratio (height-to-width)

FG_LIGHT = "#57606a"       # readable on GitHub light
FG_DARK = "#c9d1d9"        # readable on GitHub dark
ACCENT = "#58a6ff"         # cyber blue accent
ACCENT_GREEN = "#3fb950"   # status green
CHAR_W = 7.74              # 0.600 em at FONT_SIZE
FONT_SIZE = 12.9
LINE_H = 15
ROW_DELAY = 0.07           # per-row wipe stagger in seconds
FAMILY = "JBMono,ui-monospace,SFMono-Regular,Menlo,Consolas,&apos;Liberation Mono&apos;,monospace"

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(HERE, "fonts", "jbmono-ramp.woff2")


def prep(path, crop=None, clahe_clip=CLAHE_CLIP, curve=CURVE):
    """Cut out the background, smooth skin while preserving edges, apply CLAHE and power curve."""
    src = Image.open(path).convert("RGBA")
    if crop:
        src = src.crop(crop)

    cut = remove(src)
    alpha = np.array(cut.split()[-1])

    white = Image.new("RGBA", cut.size, (255, 255, 255, 255))
    gray = np.array(Image.alpha_composite(white, cut).convert("L"))

    gray = cv2.bilateralFilter(gray, 9, 40, 40)
    gray = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8)).apply(gray)
    gray = (255.0 * (gray / 255.0) ** curve).astype("uint8")
    gray[alpha < 20] = 255
    return Image.fromarray(gray)


def to_lines(img, cols=COLS, gamma=GAMMA):
    w, h = img.size
    rows = int(cols * (h / w) * ROW_RATIO)
    downscaled = img.resize((cols, rows), Image.LANCZOS)
    px = np.array(downscaled).flatten()
    n = len(RAMP)

    out = []
    for r in range(rows):
        out.append("".join(
            RAMP[min(n - 1, int((1 - px[r * cols + c] / 255.0) ** gamma * n))]
            for c in range(cols)
        ).rstrip())

    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def build_svg(lines, cols=COLS, font_path=FONT_PATH):
    pad_x = 18
    pad_top = 36
    pad_bottom = 32
    width = int(cols * CHAR_W + pad_x * 2)
    height = int(len(lines) * LINE_H + pad_top + pad_bottom)
    total_type_time = len(lines) * ROW_DELAY

    font_rule = ""
    if font_path and os.path.exists(font_path):
        with open(font_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        font_rule = (f"@font-face{{font-family:JBMono;font-style:normal;"
                     f"font-weight:400;font-display:block;"
                     f"src:url(data:font/woff2;base64,{b64}) format(&apos;woff2&apos;)}}")

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" fill="none" font-family="{FAMILY}">',
        f'<style>{font_rule}',
        f'.t-bg{{fill:#ffffff;stroke:#d0d7de;stroke-width:1}}',
        f'.t-hdr{{fill:#f6f8fa;stroke:#d0d7de;stroke-width:1}}',
        f'.t-dot-r{{fill:#ff5f56}}.t-dot-y{{fill:#ffbd2e}}.t-dot-g{{fill:#27c93f}}',
        f'.t-title{{fill:#57606a;font-size:11px;font-weight:500}}',
        f'.a{{fill:{FG_LIGHT}}}',
        f'.cur{{fill:{ACCENT};opacity:0.8}}',
        f'.t-prompt{{fill:#57606a;font-size:11.5px}}',
        f'.t-p-acc{{fill:{ACCENT};font-weight:600}}',
        f'@media(prefers-color-scheme:dark){{',
        f'.t-bg{{fill:#0d1117;stroke:#30363d}}',
        f'.t-hdr{{fill:#161b22;stroke:#30363d}}',
        f'.t-title{{fill:#8b949e}}',
        f'.a{{fill:{FG_DARK}}}',
        f'.cur{{fill:{ACCENT};opacity:0.9}}',
        f'.t-prompt{{fill:#8b949e}}',
        f'.t-p-acc{{fill:{ACCENT}}}',
        f'}}',
        f'</style>',
        
        # Terminal Header Bar
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="8" class="t-bg"/>',
        f'<path d="M1 9a8 8 0 0 1 8-8h{width - 18}a8 8 0 0 1 8 8v19H1z" class="t-hdr"/>',
        f'<circle cx="16" cy="14" r="4.5" class="t-dot-r"/>',
        f'<circle cx="29" cy="14" r="4.5" class="t-dot-y"/>',
        f'<circle cx="42" cy="14" r="4.5" class="t-dot-g"/>',
        f'<text x="{width / 2}" y="17.5" text-anchor="middle" class="t-title">aditi22builds ~ profile.sh</text>',

        # Luminous Scanline Definition
        f'<defs>',
        f'<linearGradient id="scanline" x1="0" y1="0" x2="0" y2="1">',
        f'<stop offset="0%" stop-color="#ffffff" stop-opacity="0"/>',
        f'<stop offset="50%" stop-color="{ACCENT}" stop-opacity="0.14"/>',
        f'<stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>',
        f'</linearGradient>',
        f'</defs>',
    ]

    # Staggered Typewriter Reveal
    for i, line in enumerate(lines):
        y = pad_top + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        w = max(len(line), 1) * CHAR_W
        safe = (line.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;"))

        p.append(f'<clipPath id="c{i}"><rect x="{pad_x}" y="{y}" '
                 f'height="{LINE_H}" width="0">'
                 f'<animate attributeName="width" from="0" to="{w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'</rect></clipPath>')
        p.append(f'<g clip-path="url(#c{i})"><text xml:space="preserve" '
                 f'x="{pad_x}" y="{y + 11.2:.1f}" class="a" '
                 f'font-size="{FONT_SIZE}">{safe}</text></g>')
        
        # Cursor tracking wipe
        p.append(f'<rect y="{y + 1}" width="6" height="12" class="a" opacity="0">'
                 f'<animate attributeName="x" from="{pad_x}" to="{pad_x + w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'<set attributeName="opacity" to="0.8" begin="{begin}"/>'
                 f'<set attributeName="opacity" to="0" begin="{end}"/></rect>')

    # Continuous CRT Scanline Sweep
    p.append(f'<rect x="{pad_x}" y="{pad_top}" width="{cols * CHAR_W}" height="42" fill="url(#scanline)" opacity="0">')
    p.append(f'<animate attributeName="y" from="{pad_top - 42}" to="{pad_top + len(lines) * LINE_H}" '
             f'dur="3.8s" begin="{total_type_time:.2f}s" repeatCount="indefinite"/>')
    p.append(f'<animate attributeName="opacity" values="0;0.75;0.75;0" keyTimes="0;0.1;0.9;1" '
             f'dur="3.8s" begin="{total_type_time:.2f}s" repeatCount="indefinite"/>')
    p.append(f'</rect>')

    # Bottom Terminal Prompt with Continuous Blinking Cursor
    prompt_y = pad_top + len(lines) * LINE_H + 18
    p.append(f'<g opacity="0">')
    p.append(f'<animate attributeName="opacity" from="0" to="1" begin="{total_type_time:.2f}s" dur="0.3s" fill="freeze"/>')
    p.append(f'<text x="{pad_x}" y="{prompt_y}" class="t-prompt">'
             f'<tspan class="t-p-acc">aditi@dev</tspan>:<tspan class="t-p-acc">~</tspan>$ status --live <tspan fill="{ACCENT_GREEN}">● online</tspan></text>')
    
    cursor_x = pad_x + 285
    p.append(f'<rect x="{cursor_x}" y="{prompt_y - 10}" width="7" height="13" class="cur">')
    p.append(f'<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite" begin="{total_type_time:.2f}s"/>')
    p.append(f'</rect>')
    p.append(f'</g>')

    p.append("</svg>")
    return "".join(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("photo", nargs="?", default=os.path.join(os.path.dirname(HERE), "assets", "profile.jpg"))
    ap.add_argument("out", nargs="?", default=os.path.join(os.path.dirname(HERE), "ascii.svg"))
    ap.add_argument("--crop", default="20,140,588,860", help="left,top,right,bottom bounding box")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--clahe", type=float, default=CLAHE_CLIP)
    ap.add_argument("--curve", type=float, default=CURVE)
    ap.add_argument("--preview", action="store_true", help="print ASCII preview to stdout")
    args = ap.parse_args()

    crop = None
    if args.crop:
        parts = [int(v.strip()) for v in args.crop.split(",")]
        if len(parts) != 4:
            sys.exit("--crop requires 4 integers: left,top,right,bottom")
        crop = tuple(parts)

    print(f"Processing {args.photo} -> {args.out}...")
    img = prep(args.photo, crop=crop, clahe_clip=args.clahe, curve=args.curve)
    lines = to_lines(img, cols=args.cols)

    if args.preview:
        print("\n".join(lines))

    svg_content = build_svg(lines, cols=args.cols)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"Successfully wrote {args.out} ({len(lines)} rows, {args.cols} cols, {len(svg_content)} bytes).")


if __name__ == "__main__":
    main()
