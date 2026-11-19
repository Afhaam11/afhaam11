#!/usr/bin/env python3
"""Turn a photograph into the contour portrait (writes scripts/portrait_override.json).

    python scripts/portrait_from_photo.py photo.jpg [--mask mask.png] [--crop L,T,R,B] [--flip]
    python scripts/build_assets.py --only portrait cover

Use a head-and-shoulders photo against a plain, light backdrop, or pass a mask (white = person).
The portrait faces left on the cover; use --flip if the photo faces right.
Delete scripts/portrait_override.json to go back to the abstract portrait.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_assets as ba


def person_mask(rgb):
    """Plain-backdrop cut-out: colour distance from the corners, cleaned up, largest blob, holes filled."""
    h, w = rgb.shape[:2]; k = max(4, min(h, w) // 12)
    corners = np.concatenate([rgb[:k, :k].reshape(-1, 3), rgb[:k, -k:].reshape(-1, 3)])
    d = np.sqrt(((rgb.astype(float) - np.median(corners, axis=0)) ** 2).sum(2))
    m = ndi.binary_closing(ndi.binary_opening(d > 38, iterations=2), iterations=6)
    lab, nl = ndi.label(m)
    if nl: m = lab == (1 + int(np.argmax(ndi.sum(m, lab, range(1, nl + 1)))))
    return ndi.binary_fill_holes(m)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("photo"); ap.add_argument("--mask"); ap.add_argument("--crop"); ap.add_argument("--flip", action="store_true")
    ap.add_argument("--out", default=ba.OVERRIDE)
    a = ap.parse_args()
    box = tuple(int(v) for v in a.crop.split(",")) if a.crop else None

    def load(path, mode):
        im = Image.open(path).convert(mode)
        if box: im = im.crop(box)
        return im.transpose(Image.FLIP_LEFT_RIGHT) if a.flip else im

    im = load(a.photo, "RGB")
    mask = (np.array(load(a.mask, "L")) > 127) if a.mask else person_mask(np.array(im))
    ys, xs = np.where(mask)
    top, bot = ys.min(), ys.max()
    hx = np.where(mask[top:top + max(2, int(0.45 * (bot - top)))].any(axis=0))[0]      # the head: the top 45% of the figure
    l, r = hx.min(), hx.max()
    s = min(580.0 * ba.SS / max(1, bot - top), 380.0 * ba.SS / max(1, r - l))         # head top at y = 60, head within 380 units
    gm = ndi.zoom(np.array(im.convert("L"), float), s, order=1)
    mm = ndi.zoom(mask.astype(float), s, order=1) > 0.5
    H, W = ba.PH * ba.SS, ba.PW * ba.SS
    cm = np.zeros((H, W), bool); cg = np.full((H, W), 255.0)
    y0 = int(60 * ba.SS - top * s); x0 = int(290 * ba.SS - (l + r) / 2 * s)
    ys0, xs0 = max(0, y0), max(0, x0)
    ye, xe = min(H, y0 + mm.shape[0]), min(W, x0 + mm.shape[1])
    cm[ys0:ye, xs0:xe] = mm[ys0 - y0:ye - y0, xs0 - x0:xe - x0]
    cg[ys0:ye, xs0:xe] = gm[ys0 - y0:ye - y0, xs0 - x0:xe - x0]
    if ye < H:                                    # the photo ends above the frame: carry the last row down so the bust is cut by it
        cm[ye:, xs0:xe] = cm[ye - 1, xs0:xe]; cg[ye:, xs0:xe] = cg[ye - 1, xs0:xe]
    d = ndi.distance_transform_edt(cm) / ba.SS
    dark = 1 - ndi.gaussian_filter(cg, 3 * ba.SS) / 255.0                   # darker = higher: hair, brows, eyes tighten the lines
    F = d + 34 * dark * np.clip(d / 12, 0, 1)
    z = ndi.gaussian_filter(np.random.default_rng(7).standard_normal(F.shape), 36)
    F += 2.4 * z / z.std() * np.clip(d / 14, 0, 1)
    F = ndi.gaussian_filter(F, 5); F[~cm] = -5
    json.dump(ba.contours_from_field(F, cm.astype(np.uint8)), open(a.out, "w"), separators=(",", ":"))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
