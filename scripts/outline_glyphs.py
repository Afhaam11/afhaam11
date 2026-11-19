#!/usr/bin/env python3
"""Turn a few display strings into outlined glyph paths (scripts/glyphs.json).

Only needed when you change the display typeface or want new characters in the
wordmark. build_assets.py reads glyphs.json and never needs the font itself.

    python scripts/outline_glyphs.py /path/to/Font.otf

Requires fontTools (pip install fonttools). The font in glyphs.json is
Latin Modern Roman 10 (GUST Font License, free to use and redistribute); outlines drawn into artwork do not
need a licence of their own, but the attribution is kept in README-DESIGN.md.
"""
import json, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,:;/-\u2013\u2014\u00b7& "

def main(path, out="scripts/glyphs.json"):
    font = TTFont(path)
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    data = {"upm": font["head"].unitsPerEm, "cap": getattr(font["OS/2"], "sCapHeight", 0), "glyphs": {}}
    for ch in CHARS:
        if ord(ch) not in cmap:
            continue
        g = gs[cmap[ord(ch)]]
        pen = SVGPathPen(gs, ntos=lambda v: ("%d" % round(v)))
        g.draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))        # flip y for SVG
        data["glyphs"][ch] = {"adv": g.width, "d": pen.getCommands()}
    json.dump(data, open(out, "w"), separators=(",", ":"))
    print("wrote", out, len(data["glyphs"]), "glyphs, upm", data["upm"], "cap", data["cap"])

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/texmf/fonts/opentype/public/lm/lmroman10-regular.otf")
