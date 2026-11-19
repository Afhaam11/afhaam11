"""Shared drawing helpers for the field-journal artwork: palettes, SVG primitives, outlined display type
and the plate drawing kit. Pure Python (standard library only), so the activity workflow can use it without installing anything."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, "glyphs.json"), encoding="utf-8"))

# ------------------------------------------------------------------ design tokens
LIGHT = dict(tag="", paper="#F7F7F4", paper2="#EEEEEA", ink="#191919", ink2="#555555",
             mute="#858585", rule="#D4D4CF", strong="#A7A7A0", panel="#202020", panel_text="#F5F5F1")
DARK = dict(tag="-dark", paper="#202020", paper2="#2A2A28", ink="#F5F5F1", ink2="#BDBDB6",
            mute="#8C8C86", rule="#3C3C39", strong="#66665F", panel="#F7F7F4", panel_text="#191919")
SERIF = "'Iowan Old Style','Palatino Linotype',Palatino,'Book Antiqua',Georgia,'Times New Roman',serif"
MONO = ("'IBM Plex Mono','JetBrains Mono','SF Mono',SFMono-Regular,ui-monospace,Menlo,Consolas,"
        "'DejaVu Sans Mono','Liberation Mono',monospace")
SANS = "'IBM Plex Sans','Helvetica Neue',Helvetica,Arial,'Segoe UI',system-ui,sans-serif"

# ------------------------------------------------------------------ small SVG helpers
def n(v):
    s = ("%.1f" % v)
    return s[:-2] if s.endswith(".0") else s

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def svg_doc(w, h, title, desc, body, uid):
    css = ".s{font-family:%s}.m{font-family:%s}.a{font-family:%s}" % (SERIF, MONO, SANS)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" '
            'aria-labelledby="%s-t %s-d"><title id="%s-t">%s</title><desc id="%s-d">%s</desc><style>%s</style>%s</svg>\n'
            % (w, h, w, h, uid, uid, uid, esc(title), uid, esc(desc), css, body))

def text(x, y, s, size, fill, cls="m", anchor="start", ls=0, italic=False, weight=None, op=None):
    a = 'x="%s" y="%s" font-size="%s" class="%s" fill="%s"' % (n(x), n(y), n(size), cls, fill)
    if anchor != "start": a += ' text-anchor="%s"' % anchor
    if ls: a += ' letter-spacing="%s"' % n(ls)
    if italic: a += ' font-style="italic"'
    if weight: a += ' font-weight="%s"' % weight
    if op is not None: a += ' fill-opacity="%s"' % op
    return "<text %s>%s</text>" % (a, esc(s))

def line(x1, y1, x2, y2, stroke, w=1, dash=None, cap="butt"):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s stroke-linecap="%s"/>' % (
        n(x1), n(y1), n(x2), n(y2), stroke, n(w), d, cap)

def glyph_text(s, x, y, size, fill, tracking=0.0, stroke=0.0):
    """Outlined display type. tracking is in em. Returns (svg, width_px)."""
    k = size / G["upm"]; cx = 0.0; parts = []
    for ch in s:
        g = G["glyphs"][ch]
        if ch != " ": parts.append('<path transform="translate(%s 0)" d="%s"/>' % (n(cx), g["d"]))
        cx += g["adv"] + tracking * G["upm"]
    st = ' stroke="%s" stroke-width="%s" stroke-linejoin="round"' % (fill, n(stroke / k)) if stroke else ""
    return ('<g transform="translate(%s %s) scale(%.5f)" fill="%s"%s>%s</g>' % (n(x), n(y), k, fill, st, "".join(parts)),
            (cx - tracking * G["upm"]) * k)


def smooth_d(pts, closed):
    """Quadratic-midpoint smoothing: compact path data, no corners."""
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    f = lambda p: "%s %s" % (n(p[0]), n(p[1]))
    m = len(pts)
    if closed:
        s = "M" + f(mid(pts[-1], pts[0]))
        for i in range(m):
            s += "Q" + f(pts[i]) + " " + f(mid(pts[i], pts[(i + 1) % m]))
        return s + "Z"
    s = "M" + f(pts[0])
    for i in range(1, m - 1):
        s += "Q" + f(pts[i]) + " " + f(mid(pts[i], pts[i + 1]))
    return s + "L" + f(pts[-1])


def crosshair(x, y, pal, r=5):
    return ('<g fill="none" stroke="%s" stroke-width="0.9"><circle cx="%s" cy="%s" r="%s"/>%s%s</g>'
            % (pal["strong"], n(x), n(y), n(r), line(x - r - 3, y, x + r + 3, y, pal["strong"], 0.9),
               line(x, y - r - 3, x, y + r + 3, pal["strong"], 0.9)))


# ------------------------------------------------------------------ drawing kit for the study plates
def arrow(pts, col, w=1.3, dash=None, head=7):
    d = "M" + "L".join("%s %s" % (n(x), n(y)) for x, y in pts)
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    ux, uy = (x1 - x0) / L, (y1 - y0) / L; px, py = -uy, ux
    a = (x1 - head * ux + 0.42 * head * px, y1 - head * uy + 0.42 * head * py)
    b = (x1 - head * ux - 0.42 * head * px, y1 - head * uy - 0.42 * head * py)
    da = ' stroke-dasharray="%s"' % dash if dash else ""
    return ('<path d="%s" fill="none" stroke="%s" stroke-width="%s"%s stroke-linejoin="round"/>'
            '<path d="M%s %sL%s %sL%s %sZ" fill="%s"/>'
            % (d, col, n(w), da, n(x1), n(y1), n(a[0]), n(a[1]), n(b[0]), n(b[1]), col))

def box(x, y, w, h, title, subs, pal, solid=False, size=13):
    out = ['<rect x="%s" y="%s" width="%s" height="%s" rx="2" fill="%s" stroke="%s" stroke-width="1.3"/>'
           % (n(x), n(y), n(w), n(h), pal["paper2"] if not solid else pal["panel"], pal["ink"] if not solid else pal["panel"])]
    tc = pal["ink"] if not solid else pal["panel_text"]
    sc = pal["mute"] if not solid else pal["panel_text"]
    lines = len(subs); top = y + h / 2 - (lines * 7.5) + 1
    out.append(text(x + w / 2, top + 5, title, size, tc, anchor="middle", ls=1.4))
    for i, sub in enumerate(subs):
        out.append(text(x + w / 2, top + 5 + 17 * (i + 1), sub, size - 2.5, sc, anchor="middle", ls=0.6))
    return "".join(out)

def mtext(x, y, parts, size, fill, anchor="start", ls=0, cls="s", italic=True):
    """Text with subscripts: parts = [("T", ""), ("r", "sub"), ...]."""
    inner = ""
    for t, mode in parts:
        if mode == "sub": inner += '<tspan font-size="%s" dy="%s">%s</tspan><tspan dy="%s"></tspan>' % (n(size * 0.7), n(size * 0.18), esc(t), n(-size * 0.18))
        else: inner += esc(t)
    a = 'x="%s" y="%s" font-size="%s" class="%s" fill="%s"' % (n(x), n(y), n(size), cls, fill)
    if anchor != "start": a += ' text-anchor="%s"' % anchor
    if ls: a += ' letter-spacing="%s"' % n(ls)
    if italic: a += ' font-style="italic"'
    return "<text %s>%s</text>" % (a, inner)

def plate_frame(W, H, pal):
    return ('<rect width="%d" height="%d" fill="%s"/>' % (W, H, pal["paper"]) +
            '<rect x="14" y="14" width="%d" height="%d" fill="none" stroke="%s" stroke-width="1.2"/>' % (W - 28, H - 28, pal["strong"]) +
            '<rect x="20" y="20" width="%d" height="%d" fill="none" stroke="%s" stroke-width=".8"/>' % (W - 40, H - 40, pal["rule"]))

def plate_header(label, l1, l2, tags, W, pal, cap=""):
    return (text(56, 66, label, 13, pal["ink2"], ls=3.2) + (text(W - 56, 66, cap, 11, pal["mute"], anchor="end", ls=1.8) if cap else "") +
            text(56, 108, l1, 31, pal["ink"], cls="s") + text(56, 146, l2, 31, pal["ink"], cls="s") +
            text(56, 178, tags, 12, pal["ink2"], ls=2.2) + line(56, 196, W - 56, 196, pal["strong"], 0.8))

