#!/usr/bin/env python3
"""Turn a photo into ascii.svg — a self-typing, monochrome ASCII portrait.

Generates an animated SMIL SVG with embedded JetBrains Mono font subset.

Usage:
    pip install pillow numpy opencv-python-headless rembg onnxruntime
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

FG_LIGHT = "#6e7681"       # readable on GitHub light
FG_DARK = "#c9d1d9"        # readable on GitHub dark
CHAR_W = 7.74              # 0.600 em at FONT_SIZE
FONT_SIZE = 12.9
LINE_H = 15
ROW_DELAY = 0.08           # per-row wipe stagger in seconds
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
    pad = 14
    width = int(cols * CHAR_W + pad * 2)
    height = len(lines) * LINE_H + pad * 2

    font_rule = ""
    if font_path and os.path.exists(font_path):
        with open(font_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        font_rule = (f"@font-face{{font-family:JBMono;font-style:normal;"
                     f"font-weight:400;font-display:block;"
                     f"src:url(data:font/woff2;base64,{b64}) format(&apos;woff2&apos;)}}")

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
         f'height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family="{FAMILY}">',
         f'<style>{font_rule}.a{{fill:{FG_LIGHT}}}'
         f'@media(prefers-color-scheme:dark){{.a{{fill:{FG_DARK}}}}}</style>']

    for i, line in enumerate(lines):
        y = pad + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        w = max(len(line), 1) * CHAR_W
        safe = (line.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;"))

        p.append(f'<clipPath id="c{i}"><rect x="{pad}" y="{y}" '
                 f'height="{LINE_H}" width="0">'
                 f'<animate attributeName="width" from="0" to="{w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'</rect></clipPath>')
        p.append(f'<g clip-path="url(#c{i})"><text xml:space="preserve" '
                 f'x="{pad}" y="{y + 11.2:.1f}" class="a" '
                 f'font-size="{FONT_SIZE}">{safe}</text></g>')
        p.append(f'<rect y="{y + 1}" width="6" height="12" class="a" opacity="0">'
                 f'<animate attributeName="x" from="{pad}" to="{pad + w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'<set attributeName="opacity" to="0.8" begin="{begin}"/>'
                 f'<set attributeName="opacity" to="0" begin="{end}"/></rect>')

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
