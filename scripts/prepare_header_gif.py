#!/usr/bin/env python3
"""Fit a contour-portrait GIF to the header plate for one theme.

    python scripts/prepare_header_gif.py dark-portrait.gif  --theme dark     # light lines on black  -> assets/contour-portrait-dark.gif
    python scripts/prepare_header_gif.py light-portrait.gif --theme light    # dark lines on light   -> assets/contour-portrait.gif

Maps the GIF's tones to the design tokens, scales it to the 560 x 560 plate that sits beside the cover sheet
(bottom-aligned, so the bust bleeds off the edge) and keeps the original timing and looping.
  dark  theme: black -> #202020 (dark panel), white lines -> #F5F5F1
  light theme: black lines -> #191919 (ink), the light background -> #EEEEEA (secondary paper, a faint plate on the sheet)
Requires Pillow only. The subject is never mirrored: the portrait faces right, which is why the plate sits on the left.
"""
import argparse, collections, os
from PIL import Image, ImageSequence

PLATE = 560
THEMES = {"dark": dict(lo=(0x20, 0x20, 0x20), hi=(0xF5, 0xF5, 0xF1), out="contour-portrait-dark.gif"),
          "light": dict(lo=(0x19, 0x19, 0x19), hi=(0xEE, 0xEE, 0xEA), out="contour-portrait.gif")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source"); ap.add_argument("--theme", choices=THEMES, required=True)
    ap.add_argument("--out"); ap.add_argument("--align", choices=("bottom", "center"), default="bottom")
    a = ap.parse_args()
    t = THEMES[a.theme]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", t["out"])
    src = Image.open(a.source)
    top = 255
    if a.theme == "light":                         # the light background level, so it becomes exactly the plate colour
        top = collections.Counter(src.convert("L").tobytes()).most_common(1)[0][0]
    ramp = []
    for v in range(256):
        k = min(v, top) / float(top)
        ramp += [round(t["lo"][c] + (t["hi"][c] - t["lo"][c]) * k) for c in range(3)]
    frames, durs = [], []
    for fr in ImageSequence.Iterator(src):
        durs.append(fr.info.get("duration", 100))
        g = fr.convert("L")
        g = g.point(lambda v: 0 if v < 10 else v) if a.theme == "dark" else g.point(lambda v: top if v >= top - 3 else v)
        w, h = g.size; nh = round(h * PLATE / w)
        g = g.resize((PLATE, nh), Image.LANCZOS)
        plate = Image.new("L", (PLATE, PLATE), 0 if a.theme == "dark" else top)
        plate.paste(g, (0, PLATE - nh if a.align == "bottom" else (PLATE - nh) // 2))
        p = Image.frombytes("P", plate.size, plate.tobytes()); p.putpalette(ramp)     # one shared palette for every frame
        frames.append(p)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durs, loop=0, optimize=False, disposal=1)
    print("wrote %s: %d frames, %.2f MB" % (os.path.normpath(out), len(frames), os.path.getsize(out) / 1e6))


if __name__ == "__main__":
    main()
