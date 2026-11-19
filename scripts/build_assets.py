#!/usr/bin/env python3
"""Build the field-journal artwork: assets/*.svg (light + dark variants).

    pip install numpy scipy contourpy pillow
    python scripts/build_assets.py                 # everything
    python scripts/build_assets.py --only portrait cover

No network, no web fonts. The wordmark is drawn from outlined glyphs
(scripts/glyphs.json); all other text is live SVG text with system-font fallbacks.
Everything is deterministic: the same seed gives byte-identical files.
"""
import argparse, json, math, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
import contourpy

from fj import *                      # palettes, SVG helpers, plate drawing kit (pure Python, no numpy)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets"))

# ------------------------------------------------------------------ geometry helpers
def catmull_rom_closed(P, samples=24, alpha=0.5):
    P = np.asarray(P, float); m = len(P); out = []
    for i in range(m):
        p0, p1, p2, p3 = P[(i - 1) % m], P[i], P[(i + 1) % m], P[(i + 2) % m]
        t0 = 0.0
        t1 = t0 + np.linalg.norm(p1 - p0) ** alpha
        t2 = t1 + np.linalg.norm(p2 - p1) ** alpha
        t3 = t2 + np.linalg.norm(p3 - p2) ** alpha
        t = np.linspace(t1, t2, samples, endpoint=False)[:, None]
        A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
        B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
        out.append((t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2)
    return np.vstack(out)

def rdp(pts, eps):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; ab = b - a; L = math.hypot(ab[0], ab[1])
    d = (np.hypot(*(pts - a).T) if L == 0 else
         np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / L)
    i = int(np.argmax(d))
    if d[i] > eps:
        l, r = rdp(pts[:i + 1], eps), rdp(pts[i:], eps)
        return np.vstack([l[:-1], r])
    return np.vstack([a, b])

# ------------------------------------------------------------------ the contour portrait
PW, PH, SS = 520, 640, 2          # canvas units, supersampling for the field
# A stylised, non-identifying head-and-shoulders profile (facing left). It extends below / right of the
# canvas on purpose: the bust is cut by the frame, like a map sheet, instead of ending in a hard edge.
SIL = [(292, 60), (236, 74), (198, 108), (178, 152), (170, 196), (166, 224), (176, 248), (168, 272), (156, 298),
       (140, 322), (158, 337), (155, 354), (163, 367), (156, 381), (167, 396), (158, 419), (173, 441), (214, 451),
       (250, 451), (270, 468), (276, 508), (271, 552), (252, 592), (214, 642), (168, 720), (560, 760), (600, 680),
       (560, 660), (500, 632), (448, 604), (402, 568), (374, 520), (366, 470), (394, 428), (428, 372), (446, 318),
       (448, 262), (434, 196), (402, 128), (356, 82)]

def _bump(X, Y, cx, cy, sx, sy, a):
    return a * np.exp(-(((X - cx) / sx) ** 2 + ((Y - cy) / sy) ** 2) / 2)

def _ridge(X, Y, p, q, w, a):
    px, py = p; qx, qy = q; dx, dy = qx - px, qy - py
    t = np.clip(((X - px) * dx + (Y - py) * dy) / (dx * dx + dy * dy), 0, 1)
    d2 = (X - (px + t * dx)) ** 2 + (Y - (py + t * dy)) ** 2
    return a * np.exp(-d2 / (2 * w * w))

def _ring(X, Y, cx, cy, rx, ry, a, w=0.24):
    r = np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)
    return a * np.exp(-((r - 1) ** 2) / (2 * w * w))

def contours_from_field(F, mask, step=6.8):
    """Equal-interval contour lines of a field F (canvas PWxPH, supersampled by SS), plus the silhouette of mask.
    Returns four tonal bands of thin lines, four of index (heavy) lines, and the outline, as SVG path data."""
    xs = np.arange(PW * SS) / SS; ys = np.arange(PH * SS) / SS
    gen = contourpy.contour_generator(xs, ys, F, line_type=contourpy.LineType.Separate)
    levels = np.arange(7.0, F.max(), step)
    bands = [[], [], [], []]; heavy = [[], [], [], []]
    for k, lv in enumerate(levels):
        b = min(3, int(4 * k / len(levels)))
        for ln in gen.lines(lv):
            if len(ln) < 12: continue
            closed = bool(np.allclose(ln[0], ln[-1]))
            p = rdp(ln, 0.45)
            if closed and len(p) > 3: p = p[:-1]
            if len(p) < 3: continue
            (heavy if k % 5 == 4 else bands)[b].append(smooth_d(p, closed))
    outline = []
    mg = contourpy.contour_generator(xs, ys, ndi.gaussian_filter(mask.astype(float), 2), line_type=contourpy.LineType.Separate)
    for ln in mg.lines(0.5):
        if len(ln) < 12: continue
        closed = bool(np.allclose(ln[0], ln[-1])); p = rdp(ln, 0.35)
        outline.append(smooth_d(p[:-1] if closed else p, closed))
    return dict(bands=bands, heavy=heavy, outline=outline)

def portrait_geometry(seed=7, step=6.8):
    poly = catmull_rom_closed(SIL, 28)
    im = Image.new("L", (PW * SS, PH * SS), 0)
    ImageDraw.Draw(im).polygon([tuple(p) for p in (poly * SS)], fill=1)
    mask = np.array(im, dtype=np.uint8)
    d = ndi.distance_transform_edt(mask) / SS                       # inches-from-the-edge, in canvas units
    Y, X = np.mgrid[0:PH * SS, 0:PW * SS].astype(float) / SS
    F = d.copy()
    F += _bump(X, Y, 318, 212, 96, 104, 38)                         # cranial dome
    F += _bump(X, Y, 236, 336, 44, 48, 16)                          # cheek
    F += _bump(X, Y, 189, 257, 14, 10, -17)                         # eye socket
    F += _bump(X, Y, 151, 312, 10, 16, 9)                           # nose
    F += _bump(X, Y, 160, 367, 9, 7, -9)                            # mouth
    F += _ridge(X, Y, (170, 230), (214, 236), 7, 10)                # brow
    F += _ridge(X, Y, (206, 322), (290, 302), 9, 9)                 # cheekbone
    F += _ridge(X, Y, (254, 447), (334, 354), 11, 14)               # jaw line
    F += _ridge(X, Y, (354, 330), (270, 522), 16, 13)               # neck muscle
    F += _ring(X, Y, 344, 292, 29, 21, 19, 0.30)                    # ear
    F += _bump(X, Y, 344, 296, 9, 8, -9)                            # ear hollow
    rng = np.random.default_rng(seed)
    for sig, amp in ((36, 2.8), (12, 0.9)):                         # slow undulation: no two lines alike
        z = ndi.gaussian_filter(rng.standard_normal(F.shape), sig); z /= z.std()
        F += amp * z * np.clip(d / 14, 0, 1)
    dens = 1 + 0.26 * (1 - X / PW) - 0.22 * np.clip((Y - 420) / 220, 0, 1)   # denser at the face, looser at the base
    F = ndi.gaussian_filter(F * dens, 5)
    F[mask == 0] = -5
    return contours_from_field(F, mask, step)

OVERRIDE = os.environ.get("FJ_PORTRAIT_OVERRIDE", os.path.join(HERE, "portrait_override.json"))
_PORTRAIT_CACHE = {}
def portrait_data(seed=7):
    if os.path.exists(OVERRIDE):                       # a portrait derived from a photograph
        return json.load(open(OVERRIDE, encoding="utf-8"))
    if seed not in _PORTRAIT_CACHE: _PORTRAIT_CACHE[seed] = portrait_geometry(seed)
    return _PORTRAIT_CACHE[seed]

def portrait_group(pal, x=0.0, y=0.0, scale=1.0, seed=7):
    g = portrait_data(seed)
    cols = [pal["ink"], pal["ink"], pal["ink2"], pal["mute"]]
    parts = ['<g transform="translate(%s %s) scale(%.4f)" fill="none" stroke-linecap="round" stroke-linejoin="round">' % (n(x), n(y), scale)]
    for b in range(4):
        if g["bands"][b]: parts.append('<path stroke="%s" stroke-width="1.25" d="%s"/>' % (cols[b], "".join(g["bands"][b])))
        if g["heavy"][b]: parts.append('<path stroke="%s" stroke-width="2" d="%s"/>' % (cols[b], "".join(g["heavy"][b])))
    parts.append('<path stroke="%s" stroke-width="2.6" d="%s"/>' % (pal["ink"], "".join(g["outline"])))
    parts.append("</g>")
    return "".join(parts)

def build_portrait(pal):
    body = portrait_group(pal)
    return svg_doc(PW, PH, "Contour portrait",
                   "An abstract, non-identifying human head and shoulders in profile, drawn as topographic contour lines: "
                   "outer lines follow the silhouette, inner lines trace the cranium, brow, cheek, jaw, ear and neck.",
                   body, "portrait")


# ------------------------------------------------------------------ the cover
def ruler(x0, x1, y, pal, step=10, majors=10, up=True, labels=True):
    out = [line(x0, y, x1, y, pal["strong"], 0.8)]
    i = 0
    while x0 + i * step <= x1 + 0.1:
        x = x0 + i * step; major = i % majors == 0
        ln = 9 if major else 4
        out.append(line(x, y, x, y - ln if up else y + ln, pal["strong"] if major else pal["rule"], 0.8))
        if major and labels:
            out.append(text(x, y + 14, "%02d" % (i // majors), 9, pal["mute"], anchor="middle"))
        i += 1
    return "".join(out)

def build_cover_inline(pal):
    W, H = 1200, 560
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    b = ['<rect width="%d" height="%d" fill="%s"/>' % (W, H, pal["paper"]),
         '<rect x="14" y="14" width="%d" height="%d" fill="none" stroke="%s" stroke-width="1.2"/>' % (W - 28, H - 28, strong),
         '<rect x="20" y="20" width="%d" height="%d" fill="none" stroke="%s" stroke-width=".8"/>' % (W - 40, H - 40, rule)]
    b.append(ruler(64, 1136, 44, pal))
    s = (H - 40) / PH                                   # the bust is cut by the inner frame, like a map sheet
    b.append(portrait_group(pal, W - 20 - PW * s, 20, s))
    b.append(text(64, 92, "FIELD JOURNAL / 001", 13, ink2, ls=3.2))
    b.append(line(300, 88, 372, 88, strong, 0.8))
    wm, wmw = glyph_text("AFHAAM.", 62, 262, 136, ink, tracking=0.035, stroke=0.7)
    b.append(wm)
    b.append(text(66, 318, "Computer Science Engineer", 36, ink, cls="s", italic=True))
    b.append(line(64, 348, 704, 348, strong, 0.8))
    b.append(text(64, 382, "MACHINE LEARNING / ARTIFICIAL INTELLIGENCE", 15, ink2, ls=2.6))
    b.append(text(64, 408, "RESEARCH / EXPERIMENTS", 15, ink2, ls=2.6))
    b.append(text(64, 478, "COMPUTER SCIENCE\u00a0\u00a0/\u00a0\u00a0INDEPENDENT EXPERIMENTS\u00a0\u00a0/\u00a0\u00a0OBSERVE \u00b7 EXPERIMENT \u00b7 ITERATE", 12, mute, ls=2.2))
    # measurement scale
    sy = 520
    b.append(line(64, sy, 244, sy, strong, 0.9))
    for i in range(7):
        b.append(line(64 + i * 30, sy, 64 + i * 30, sy - (8 if i % 3 == 0 else 4), strong, 0.9))
    for i, lab in ((0, "0"), (3, "5"), (6, "10")):
        b.append(text(64 + i * 30, sy + 14, lab, 9, mute, anchor="middle"))
    b.append(text(256, sy + 3, "ARBITRARY UNITS", 9, mute, ls=2))
    b.append(text(738, 520, "FIG. 0 \u00b7 CONTOUR STUDY", 11, mute, ls=2.4))
    b.append(crosshair(14, 280, pal)); b.append(crosshair(W - 14, 280, pal))
    return svg_doc(W, H, "Field journal cover",
                   "Cover page of an engineering field journal. The name AFHAAM in large serif capitals, "
                   "'Computer Science Engineer' beneath it, then machine learning, artificial intelligence, research and "
                   "experiments. On the right, an abstract contour-line portrait of a head and shoulders in profile, "
                   "drawn like a topographic map.", "".join(b), "cover")



def build_cover(pal):
    """The paper sheet of the split header. The animated portrait plate (assets/contour-portrait.gif) sits to its left."""
    W, H = 760, 560
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    b = ['<rect width="%d" height="%d" fill="%s"/>' % (W, H, pal["paper"]),
         '<rect x="14" y="14" width="%d" height="%d" fill="none" stroke="%s" stroke-width="1.2"/>' % (W - 28, H - 28, strong),
         '<rect x="20" y="20" width="%d" height="%d" fill="none" stroke="%s" stroke-width=".8"/>' % (W - 40, H - 40, rule)]
    b.append(ruler(64, 696, 44, pal))
    b.append(text(64, 92, "FIELD JOURNAL / 001", 13, ink2, ls=3.2))
    b.append(line(300, 88, 372, 88, strong, 0.8))
    wm, wmw = glyph_text("AFHAAM.", 62, 262, 122, ink, tracking=0.035, stroke=0.7)
    b.append(wm)
    b.append(text(66, 318, "Computer Science Engineer", 36, ink, cls="s", italic=True))
    b.append(line(64, 348, 696, 348, strong, 0.8))
    b.append(text(64, 382, "MACHINE LEARNING / ARTIFICIAL INTELLIGENCE", 15, ink2, ls=2.6))
    b.append(text(64, 408, "RESEARCH / EXPERIMENTS", 15, ink2, ls=2.6))
    b.append(text(64, 478, "COMPUTER SCIENCE\u00a0\u00a0/\u00a0\u00a0INDEPENDENT EXPERIMENTS\u00a0\u00a0/\u00a0\u00a0OBSERVE \u00b7 EXPERIMENT \u00b7 ITERATE", 12, mute, ls=0.8))
    sy = 520
    b.append(line(64, sy, 244, sy, strong, 0.9))
    for i in range(7):
        b.append(line(64 + i * 30, sy, 64 + i * 30, sy - (8 if i % 3 == 0 else 4), strong, 0.9))
    for i, lab in ((0, "0"), (3, "5"), (6, "10")):
        b.append(text(64 + i * 30, sy + 14, lab, 9, mute, anchor="middle"))
    b.append(text(256, sy + 3, "ARBITRARY UNITS", 9, mute, ls=2))
    b.append(text(W - 44, 520, "\u2190 FIG. 0 \u00b7 CONTOUR PORTRAIT", 11, mute, anchor="end", ls=2.4))
    b.append(crosshair(14, 280, pal)); b.append(crosshair(W - 14, 280, pal))
    return svg_doc(W, H, "Field journal cover",
                   "Paper sheet of a field journal cover. The name AFHAAM in large serif capitals, 'Computer Science Engineer' beneath it, "
                   "then machine learning, artificial intelligence, research and experiments, with a ruler along the top and a measurement scale "
                   "at the bottom. Beside it, an animated contour portrait.", "".join(b), "cover")

# ------------------------------------------------------------------ study 001: the reactor
def vessel(cx, pal):
    ink, mute, strong, rule = pal["ink"], pal["mute"], pal["strong"], pal["rule"]
    o = []
    o.append('<g fill="none" stroke="%s" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round">' % ink)
    o.append('<path d="M%s 282V478Q%s 522 %s 522H%sQ%s 522 %s 478V282"/>' % (n(cx - 72), n(cx - 72), n(cx - 30), n(cx + 30), n(cx + 72), n(cx + 72)))   # jacket
    o.append('<path d="M%s 270V470Q%s 502 %s 502H%sQ%s 502 %s 470V270"/>' % (n(cx - 50), n(cx - 50), n(cx - 18), n(cx + 18), n(cx + 50), n(cx + 50)))    # vessel
    o.append(line(cx - 72, 282, cx - 50, 282, ink, 1.4) + line(cx + 50, 282, cx + 72, 282, ink, 1.4))
    o.append(line(cx - 62, 262, cx + 62, 262, ink, 1.6) + line(cx - 54, 270, cx + 54, 270, ink, 1.0))   # lid
    o.append('<rect x="%s" y="236" width="24" height="16" rx="2"/>' % n(cx - 12))                          # motor
    o.append(line(cx, 252, cx, 452, ink, 1.4))                                                            # shaft
    o.append(line(cx - 24, 452, cx + 24, 452, ink, 1.6) + line(cx - 24, 452, cx - 28, 462, ink, 1.4) + line(cx + 24, 452, cx + 28, 442, ink, 1.4))
    o.append('</g>')
    o.append('<path d="M%s 330q8 -5 16 0t16 0t16 0t16 0t16 0" fill="none" stroke="%s" stroke-width="1" stroke-dasharray="3 3"/>' % (n(cx - 48), mute))  # liquid level
    zig = "M%s 484" % n(cx - 38) + "".join("L%s %s" % (n(cx - 38 + 8 * (i + 1)), 490 if i % 2 == 0 else 478) for i in range(9))
    o.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.4" stroke-linejoin="round"/>' % (zig, ink))   # heater element
    o.append(line(cx + 32, 262, cx + 32, 396, ink, 1.0))                                                   # thermocouple
    o.append('<circle cx="%s" cy="396" r="3.4" fill="%s"/>' % (n(cx + 32), ink))
    o.append('<circle cx="%s" cy="372" r="3.4" fill="%s"/>' % (n(cx + 72), ink))                           # jacket sensor
    o.append(text(cx - 26, 360, "0.5 L", 11, mute, anchor="middle", ls=1))
    return "".join(o)

def build_reactor(pal):
    W, H = 1000, 700
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    b = [plate_frame(W, H, pal),
         plate_header("STUDY 001", "Explainable reinforcement learning", "for safe batch reactor control",
                      "PROCESS CONTROL \u00b7 PPO / UKF / SHAP \u00b7 BATCH REACTOR", W, pal, cap="FIG. 1 \u00b7 CONTROL LOOP")]
    cx = 150
    b.append(vessel(cx, pal))
    # sensing: T_r, T_j -> UKF
    b.append(line(cx + 32, 396, 262, 380, mute, 1, dash="2 3")); b.append(line(cx + 72, 372, 262, 380, mute, 1, dash="2 3"))
    b.append(arrow([(262, 380), (322, 380)], ink))
    b.append(mtext(292, 366, [("T", ""), ("r", "sub"), (", T", ""), ("j", "sub")], 15, ink, anchor="middle"))
    # observer, policy
    b.append(box(322, 336, 150, 88, "UKF", ["observer", "estimates I, M"], pal))
    b.append(arrow([(472, 380), (542, 380)], ink))
    b.append(text(507, 366, "obs", 10, mute, anchor="middle", ls=1))
    b.append(box(542, 322, 170, 116, "PPO", ["policy network", "2 \u00d7 256 hidden", "continuous actions"], pal, solid=True))
    # reference trajectory
    b.append(box(562, 212, 130, 50, "REFERENCE", ["trajectory"], pal, size=12))
    b.append(arrow([(627, 262), (627, 322)], ink))
    b.append(mtext(641, 296, [("e", "")], 14, ink))
    # reward and explainability annex
    b.append(box(764, 262, 180, 112, "REWARD", ["tracking \u00b7 cooperation", "smoothness \u00b7 MAT barrier", "estimator confidence"], pal))
    b.append(arrow([(764, 322), (712, 352)], mute, dash="3 3"))
    b.append(mtext(730, 326, [("r", "")], 14, mute))
    b.append(box(764, 400, 180, 112, "EXPLAIN", ["SHAP", "surrogate trees", "sensitivity heatmaps"], pal))
    b.append(arrow([(712, 408), (738, 408), (738, 456), (764, 456)], mute, dash="3 3"))
    # actuators
    b.append(box(522, 468, 100, 52, "COOLANT", ["pump"], pal, size=12))
    b.append(box(652, 468, 100, 52, "HEATER", ["element"], pal, size=12))
    b.append(arrow([(572, 438), (572, 468)], ink)); b.append(arrow([(702, 438), (702, 468)], ink))
    b.append(mtext(585, 458, [("u", ""), ("1", "sub")], 14, ink)); b.append(mtext(695, 458, [("H", ""), ("c", "sub")], 14, ink, anchor="end"))
    # return paths into the plant
    b.append(arrow([(572, 520), (572, 560), (290, 560), (290, 470), (cx + 72, 470)], ink))
    b.append(arrow([(702, 520), (702, 596), (cx, 596), (cx, 506)], ink))
    b.append(text(430, 552, "coolant flow  0\u20130.7 L/min", 11, ink2, anchor="middle", ls=0.6))
    b.append(text(430, 616, "heater current  8\u201320 mA", 11, ink2, anchor="middle", ls=0.6))
    # plant caption and the schematic task
    b.append(text(56, 586, "PLANT", 12, ink, ls=2.4))
    b.append(text(56, 606, "acrylamide polymerisation", 11, mute, ls=0.6))
    b.append(text(56, 624, "4-state ODE \u00b7 RK45", 11, mute, ls=0.6))
    b.append(text(56, 642, "7,200-step reference trajectory", 11, mute, ls=0.6))
    b.append(text(764, 548, "THE TASK \u00b7 SCHEMATIC", 11, ink2, ls=1.6))
    px0, py0, pw, ph = 764, 564, 180, 66
    b.append(line(px0, py0 + ph, px0 + pw, py0 + ph, strong, 1) + line(px0, py0, px0, py0 + ph, strong, 1))
    b.append(line(px0, py0 + 7, px0 + pw, py0 + 7, ink2, 1, dash="5 3"))
    b.append(text(px0 + pw, py0 + 1, "MAT", 9, mute, anchor="end", ls=1))
    ref = "M%s %s C%s %s %s %s %s %s S%s %s %s %s" % (px0 + 4, py0 + ph - 6, px0 + 38, py0 + 30, px0 + 58, py0 + 26, px0 + 96, py0 + 28, px0 + 140, py0 + 40, px0 + pw - 4, py0 + ph - 12)
    b.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.2" stroke-dasharray="4 3"/>' % (ref, mute))
    act = "M%s %s C%s %s %s %s %s %s S%s %s %s %s" % (px0 + 4, py0 + ph - 8, px0 + 36, py0 + 34, px0 + 56, py0 + 30, px0 + 96, py0 + 31, px0 + 140, py0 + 42, px0 + pw - 4, py0 + ph - 13)
    b.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.6"/>' % (act, ink))
    b.append(text(px0 + pw, py0 + ph + 14, "illustration, not measured data", 9, mute, anchor="end", ls=0.4))
    return svg_doc(W, H, "Study 001: explainable reinforcement learning for safe batch reactor control",
                   "Technical schematic of a control loop. A jacketed 0.5 litre acrylamide polymerisation batch reactor reports reactor and "
                   "jacket temperature to an unscented Kalman filter that estimates monomer and initiator concentrations. A PPO policy network "
                   "reads the estimate and the tracking error against a reference temperature trajectory, and sets coolant flow and heater "
                   "current. A reward panel feeds the policy and an explainability panel (SHAP, surrogate decision trees, sensitivity "
                   "heatmaps) reads it. A small schematic shows the task: follow a reference without crossing the maximum allowable temperature.",
                   "".join(b), "reactor")



# ------------------------------------------------------------------ study 003: the CRM agent
def sheet(pal):
    """A drawn customer spreadsheet: header band, ruled rows, and the rows a question matches marked with a bar."""
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    x0, y0, cols, hh, rh, nrows = 60, 232, (56, 72, 66, 68), 24, 24, 10
    w = sum(cols); matches = {2, 5, 6}
    o = ['<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (x0, y0, w, hh, pal["panel"])]
    cx = x0
    for lab, cw in zip(("Name", "Email", "Product", "Warranty"), cols):
        o.append(text(cx + 7, y0 + 16, lab, 10, pal["panel_text"], ls=0.4)); cx += cw
    lens = ((30, 52, 38, 40), (38, 60, 44, 36), (26, 44, 50, 44), (34, 56, 32, 48), (28, 50, 46, 38),
            (36, 58, 40, 42), (30, 48, 36, 46), (40, 62, 48, 34), (26, 54, 42, 44), (34, 46, 38, 40))
    for r in range(nrows):
        y = y0 + hh + r * rh
        if r in matches:
            o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (x0, y, w, rh, pal["paper2"]))
            o.append('<rect x="%d" y="%d" width="3" height="%d" fill="%s"/>' % (x0 - 7, y + 3, rh - 6, ink))
        cx = x0
        for c, cw in enumerate(cols):
            o.append(line(cx + 7, y + rh / 2, cx + 7 + lens[r][c], y + rh / 2, ink2 if r in matches else strong, 2, cap="round")); cx += cw
        o.append(line(x0, y + rh, x0 + w, y + rh, rule, 0.8))
    cx = x0
    for cw in cols[:-1]:
        cx += cw; o.append(line(cx, y0 + hh, cx, y0 + hh + nrows * rh, rule, 0.8))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s" stroke-width="1.4"/>' % (x0, y0, w, hh + nrows * rh, ink))
    ly = y0 + hh + nrows * rh + 30
    o.append('<rect x="%d" y="%d" width="3" height="14" fill="%s"/>' % (x0 - 7, ly - 11, ink))
    o.append(text(x0 + 4, ly, "rows the question matches", 10, ink2, ls=0.6))
    return "".join(o)

def build_crm(pal):
    W, H = 1000, 700
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    b = [plate_frame(W, H, pal),
         plate_header("STUDY 003", "Northstar CRM AI", "an agent for customer spreadsheets",
                      "LLM APPLICATION \u00b7 AGENT WORKFLOW \u00b7 DATA ANALYTICS", W, pal, cap="FIG. 3 \u00b7 QUESTION TO CAMPAIGN")]
    b.append(sheet(pal))
    b.append(text(56, 598, "SPECIMEN", 12, ink, ls=2.4))
    b.append(text(56, 620, "Customer spreadsheet \u00b7 xlsx, csv", 14, ink2, cls="s", italic=True))
    b.append(text(56, 640, "illustration, not real data", 11, mute, ls=0.6))
    bx, bw, bh = (380, 496, 612, 728, 844), 100, 56
    ya, yb = 256, 430
    A = (("QUESTION", ["plain English"], False), ("PLAN", ["LLM \u2192 JSON"], True), ("VALIDATE", ["schema check"], False),
         ("DUCKDB", ["SELECT only"], False), ("RECORDS", ["rows + SQL"], False))
    B = (("DRAFT", ["subject, body"], False), ("PREVIEW", ["per recipient"], False), ("APPROVE", ["you decide"], True),
         ("SEND", ["SendGrid"], False), ("SUMMARY", ["sent, skipped"], False))
    b.append(text(380, 242, "A \u00b7 QUESTION TO RECORDS", 11, ink2, ls=2.4))
    b.append(text(380, 414, "B \u00b7 RECORDS TO CAMPAIGN", 11, ink2, ls=2.4))
    for row, y in ((A, ya), (B, yb)):
        for x, (t, subs, solid) in zip(bx, row): b.append(box(x, y, bw, bh, t, subs, pal, solid=solid, size=12))
        for x in bx[:-1]: b.append(arrow([(x + bw, y + bh / 2), (x + bw + 16, y + bh / 2)], ink, head=6))
    # the spreadsheet is uploaded into an in-memory table
    b.append('<path d="M322 244V224H778V256" fill="none" stroke="%s" stroke-width="1" stroke-dasharray="3 3"/>' % mute)
    b.append('<path d="M778 256l-3 -7l6 0Z" fill="%s"/>' % mute)
    b.append(text(550, 219, "uploaded and held in an in-memory table", 9.5, mute, anchor="middle", ls=0.6))
    # what sits between the model and the data
    for x0, x1, l1, l2, l3 in ((380, 596, "THE MODEL NEVER WRITES SQL", "", ""), (612, 828, "FIVE SAFEGUARDS", "schema, columns, parameters", "SELECT-only, row cap")):
        b.append('<path d="M%d 322v6H%dv-6" fill="none" stroke="%s" stroke-width="1"/>' % (x0, x1, strong))
        b.append(text((x0 + x1) / 2, 344, l1, 10, ink2, anchor="middle", ls=0.8))
        if l2: b.append(text((x0 + x1) / 2, 358, l2, 9.5, mute, anchor="middle", ls=0.4)); b.append(text((x0 + x1) / 2, 371, l3, 9.5, mute, anchor="middle", ls=0.4))
    b.append(arrow([(894, ya + bh), (894, 392), (356, 392), (356, yb + bh / 2), (380, yb + bh / 2)], ink))
    # the approval gate
    b.append(arrow([(662, yb + bh), (662, yb + bh + 22)], mute, dash="3 3"))
    b.append('<g stroke-linecap="round">%s%s</g>' % (line(657, 515, 667, 525, ink, 1.4, cap="round"), line(667, 515, 657, 525, ink, 1.4, cap="round")))
    b.append(text(676, 524, "not approved: stays a draft", 11, ink2, ls=0.5))
    # audit trail
    b.append('<rect x="380" y="548" width="564" height="40" rx="2" fill="%s" stroke="%s" stroke-width="1"/>' % (pal["paper2"], strong))
    b.append(text(394, 573, "AUDIT TRAIL", 11, ink, ls=2))
    b.append(text(930, 573, "uploads \u00b7 questions (plan, SQL, rows) \u00b7 campaign events", 10, mute, anchor="end", ls=0.4))
    return svg_doc(W, H, "Study 003: Northstar CRM AI, an agent for customer spreadsheets",
                   "Technical diagram beside a drawn customer spreadsheet with a few matching rows marked. Pipeline A, question to records: a plain-English "
                   "question goes to a language model that returns a JSON query plan, never SQL; the plan is validated against the spreadsheet's columns, "
                   "parameterized SELECT-only SQL runs on an in-memory DuckDB table, and records come back with the SQL and the plan. Pipeline B, records to "
                   "campaign: the model drafts a subject and body with placeholders, each recipient's email is previewed, nothing is sent until the user approves, "
                   "sending goes through SendGrid, and a summary reports what was sent or skipped. An audit trail records uploads, questions and campaign events.",
                   "".join(b), "crm")

# ------------------------------------------------------------------ study 002: the rice leaf and the retrieval pipeline
def _bez(p, t):
    t = np.asarray(t)[:, None]
    return (1 - t) ** 3 * p[0] + 3 * (1 - t) ** 2 * t * p[1] + 3 * (1 - t) * t ** 2 * p[2] + t ** 3 * p[3]

def _bez_d(p, t):
    t = np.asarray(t)[:, None]
    return 3 * (1 - t) ** 2 * (p[1] - p[0]) + 6 * (1 - t) * t * (p[2] - p[1]) + 3 * t ** 2 * (p[3] - p[2])

def poly_d(pts, closed=False):
    return "M" + "L".join("%s %s" % (n(x), n(y)) for x, y in pts) + ("Z" if closed else "")

def leaf(pal):
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    P = [np.array(v, float) for v in ((96, 566), (92, 430), (150, 306), (304, 238))]
    t = np.linspace(0, 1, 56)
    C = _bez(P, t); D = _bez_d(P, t)
    T = D / np.linalg.norm(D, axis=1)[:, None]; N = np.c_[-T[:, 1], T[:, 0]]
    h = (13 * (0.5 + 0.5 * np.minimum(1, t / 0.18)) * (1 - np.clip((t - 0.58) / 0.42, 0, 1) ** 1.35))[:, None]
    o = ['<path d="%s" fill="%s" stroke="%s" stroke-width="1.5" stroke-linejoin="round"/>'
         % (poly_d(np.vstack([C + N * h, (C - N * h)[::-1]]), True), pal["paper2"], ink)]
    for k in (-0.6, -0.2, 0.2, 0.6):
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width=".8"/>' % (poly_d((C + N * h * k)[3:-3]), strong))
    o.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.3"/>' % (poly_d(C[1:-1]), ink2))
    for ti, k, L, Wd in ((0.27, -0.3, 20, 7), (0.44, 0.3, 24, 7.5), (0.60, -0.2, 18, 6), (0.74, 0.25, 11, 4.5)):
        i = int(ti * 55); c = C[i] + N[i] * h[i] * k; ang = math.degrees(math.atan2(T[i][1], T[i][0]))
        o.append('<g transform="translate(%s %s) rotate(%s)"><ellipse rx="%s" ry="%s" fill="none" stroke="%s" stroke-width="1"/>'
                 '<ellipse rx="%s" ry="%s" fill="%s" stroke="%s" stroke-width="1.3"/><ellipse rx="%s" ry="%s" fill="%s"/></g>'
                 % (n(c[0]), n(c[1]), n(ang), n(L / 2 + 4), n(Wd / 2 + 3), mute, n(L / 2), n(Wd / 2), pal["paper"], ink, n(L / 4), n(Wd / 5), ink2))
    i = int(0.44 * 55); c = C[i] + N[i] * h[i] * 0.3
    return "".join(o), (float(c[0]), float(c[1])), (float(C[-1][0]), float(C[-1][1]))

def build_rice(pal):
    W, H = 1000, 700
    ink, ink2, mute, rule, strong = pal["ink"], pal["ink2"], pal["mute"], pal["rule"], pal["strong"]
    b = [plate_frame(W, H, pal),
         plate_header("STUDY 002", "Rice leaf disease detection", "and a retrieval-augmented farmer assistant",
                      "COMPUTER VISION \u00b7 RETRIEVAL-AUGMENTED GENERATION \u00b7 AGRITECH", W, pal, cap="FIG. 2 \u00b7 TWO PIPELINES, ONE ASSISTANT")]
    art, lesion, tip = leaf(pal)
    b.append(art)
    b.append(line(lesion[0] + 8, lesion[1] - 4, 236, lesion[1] - 4, mute, 1)); b.append(text(242, lesion[1], "lesion", 11, ink2, ls=1))
    b.append(text(56, 598, "SPECIMEN", 12, ink, ls=2.4))
    b.append(text(56, 620, "Oryza sativa \u00b7 leaf blade", 14, ink2, cls="s", italic=True))
    b.append(text(56, 640, "schematic, not to scale", 11, mute, ls=0.6))
    # pipeline A: vision
    b.append(text(380, 238, "A \u00b7 VISION", 11, ink2, ls=2.4))
    ya, hh = 256, 56
    b.append(box(380, ya, 114, hh, "IMAGE", ["leaf photo"], pal, size=12))
    b.append(box(574, ya, 150, hh, "CLASSIFIER", ["EfficientNet-B3"], pal, solid=True, size=12))
    b.append(box(804, ya, 140, hh, "DISEASE", ["result"], pal, size=12))
    b.append('<rect x="552" y="244" width="404" height="80" rx="4" fill="none" stroke="%s" stroke-width="1.1" stroke-dasharray="5 4"/>' % ink2)
    b.append(text(560, 238, "OOD CHECK \u00b7 NON-RICE IMAGES REJECTED", 10, ink2, ls=1.6))
    b.append(arrow([(494, ya + hh / 2), (574, ya + hh / 2)], ink)); b.append(arrow([(724, ya + hh / 2), (804, ya + hh / 2)], ink))
    b.append(arrow([(tip[0] + 2, tip[1] + 6), (352, tip[1] + 6), (352, ya + hh / 2), (380, ya + hh / 2)], ink))
    b.append(arrow([(652, 324), (652, 350)], mute, dash="3 3"))
    b.append('<g stroke-linecap="round">%s%s</g>' % (line(646, 356, 656, 366, ink, 1.4, cap="round"), line(656, 356, 646, 366, ink, 1.4, cap="round")))
    b.append(text(664, 365, "rejected: not a rice leaf", 11, ink2, ls=0.5))
    # pipeline B: retrieval
    b.append(text(380, 408, "B \u00b7 RETRIEVAL", 11, ink2, ls=2.4))
    yb = 426
    b.append(box(380, yb, 104, hh, "QUESTION", ["from a farmer"], pal, size=12))
    b.append(box(514, yb, 104, hh, "RETRIEVAL", ["MMR"], pal, size=12))
    b.append(box(648, yb, 130, hh, "RERANKING", ["cross-encoder"], pal, solid=True, size=12))
    b.append(box(808, yb, 136, hh, "RESPONSE", ["grounded in sources"], pal, size=12))
    for x0, x1 in ((484, 514), (618, 648), (778, 808)): b.append(arrow([(x0, yb + hh / 2), (x1, yb + hh / 2)], ink))
    for k in range(3):
        b.append('<rect x="%s" y="%s" width="42" height="28" rx="2" fill="%s" stroke="%s" stroke-width="1.2"/>' % (n(546 + 5 * k), n(526 - 5 * k), pal["paper"], ink))
    b.append(arrow([(566, 524), (566, yb + hh)], ink, head=6))
    b.append(text(566, 572, "agricultural documents", 11, ink2, anchor="middle", ls=0.5))
    # evaluation
    b.append(line(380, 604, 944, 604, rule, 1))
    b.append(text(380, 626, "EVALUATION", 11, ink2, ls=2.4))
    b.append(text(380, 646, "agricultural images: Kaggle data and real outdoor photographs", 11, mute, ls=0.4))
    b.append(text(380, 664, "retrieval and response evaluation", 11, mute, ls=0.4))
    return svg_doc(W, H, "Study 002: rice leaf disease detection and a retrieval-augmented farmer assistant",
                   "Technical diagram with a drawn rice leaf specimen carrying spindle-shaped lesions. Pipeline A: a leaf photo goes to an "
                   "EfficientNet-B3 classifier and a disease result, with an out-of-distribution check around that stage that rejects images that are not rice leaves. "
                   "Pipeline B: a farmer's question goes through retrieval with maximal marginal relevance over agricultural documents, "
                   "cross-encoder reranking, and a response grounded in the retrieved sources.", "".join(b), "rice")

# ------------------------------------------------------------------ the divider
def build_divider(pal):
    W, H = 1000, 40; cx, cy = 500, 20
    b = [line(56, cy, cx - 36, cy, pal["rule"], 1), line(cx + 36, cy, W - 56, cy, pal["rule"], 1)]
    major, minor = [], []
    for i in range(0, 56):
        for x in (cx + 44 + i * 8, cx - 44 - i * 8):
            if 56 <= x <= W - 56: (major if i % 5 == 0 else minor).append("M%s %sv-%d" % (n(x), n(cy), 6 if i % 5 == 0 else 3))
    b.append('<path d="%s" fill="none" stroke="%s" stroke-width=".8"/>' % ("".join(minor), pal["rule"]))
    b.append('<path d="%s" fill="none" stroke="%s" stroke-width=".8"/>' % ("".join(major), pal["strong"]))
    th = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    for r0, ph, col, w in ((3.5, 0.3, pal["mute"], 1), (8, 1.2, pal["ink2"], 1), (12.5, 2.1, pal["ink2"], 1), (17, 0.7, pal["ink"], 1.3)):
        r = r0 * (1 + 0.11 * np.sin(3 * th + ph) + 0.06 * np.sin(5 * th + 2 * ph))
        pts = np.c_[cx + 1.35 * r * np.cos(th), cy + r * np.sin(th)]
        b.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (smooth_d(pts, True), col, w))
    b.append(crosshair(56, cy, pal, r=3)); b.append(crosshair(W - 56, cy, pal, r=3))
    return svg_doc(W, H, "Section divider", "A thin ruled line with measurement ticks and a small hill drawn as four irregular contour loops.", "".join(b), "divider")

# ------------------------------------------------------------------ build orchestration
JOBS = {"portrait": build_portrait, "cover": build_cover, "reactor": build_reactor, "rice": build_rice, "crm": build_crm, "divider": build_divider}

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="*", help="asset keys: " + ", ".join(JOBS))
    ap.add_argument("--out", default=OUT, help="output folder (default: assets/)")
    ap.add_argument("--inline-cover", action="store_true", help="cover with the abstract portrait inside (no GIF plate)")
    args = ap.parse_args()
    out = os.path.abspath(args.out); os.makedirs(out, exist_ok=True)
    if args.inline_cover: JOBS["cover"] = build_cover_inline
    names = {"portrait": "portrait-contour", "cover": "field-cover", "reactor": "reactor-study",
             "rice": "rice-study", "crm": "crm-study", "divider": "visual-divider"}
    for key, fn in JOBS.items():
        if args.only and key not in args.only: continue
        for pal in (LIGHT, DARK):
            path = os.path.join(out, names[key] + pal["tag"] + ".svg")
            svg = fn(pal)
            open(path, "w", encoding="utf-8", newline="\n").write(svg)
            print("wrote %-28s %6.1f KB" % (os.path.basename(path), len(svg.encode()) / 1024))

if __name__ == "__main__":
    main()
