"""Convert a photo into colored, shape-matched ASCII data for the animated scene.

Usage: python3 convert.py photo.jpg photo.regions.json scene.json [preview.png]

For each output resolution it stores, per character cell:
  - the glyph (picked by matching the cell's light/dark pattern against every ASCII glyph)
  - a color-graded base color
  - a scene class (sky / building / foliage / grass / path) used for relighting
  - a glow code (stained glass, warm window) used at night
"""
import sys, json, base64
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from segment import segment, SKY, BLD, VEG, GRS, PTH, OTH

import os
FONT = os.environ.get("ASCII_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")  # must be DejaVu Sans Mono (same font the component embeds)
LEVELS = [100, 140, 190]      # columns per resolution level
GX, GY = 5, 10                # sub-samples per cell used for shape matching
BASELINE = 0.76               # baseline position as a fraction of cell height (must match the page)
ADV = 0.602                   # DejaVu Sans Mono advance width in em

DETAIL, SHAPE, TONE_W, TLO, THI, GAMMA = 0.8, 1.3, 600.0, 0.15, 0.85, 1.25
CLASS_INK = np.array([0, 1.0, 0.8, 0.5, 0.65, 0.8])   # ink weight by class: sky, building, foliage, grass, path, other


def gradient_map(lum, stops):
    """Map luminance through a list of (position, rgb) stops."""
    pos = np.array([s[0] for s in stops], np.float32)
    cols = np.array([s[1] for s in stops], np.float32) / 255
    out = np.empty(lum.shape + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(lum, pos, cols[:, c])
    return out


GRADES = {
    BLD: ([(0.0, (38, 30, 58)), (0.25, (104, 78, 104)), (0.55, (214, 164, 122)), (0.8, (246, 206, 160)), (1.0, (255, 240, 214))], 0.7),
    VEG: ([(0.0, (6, 26, 30)), (0.2, (20, 70, 58)), (0.45, (52, 128, 72)), (0.75, (150, 196, 84)), (1.0, (220, 236, 140))], 0.7),
    GRS: ([(0.0, (18, 60, 40)), (0.3, (52, 128, 58)), (0.55, (110, 178, 64)), (0.85, (190, 226, 100)), (1.0, (232, 244, 160))], 0.65),
    PTH: ([(0.0, (36, 36, 54)), (0.5, (96, 96, 118)), (1.0, (178, 176, 196))], 0.7),
}


def grade(img, cls):
    lum = 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
    # normalize luminance per class so each gradient map spans its full range
    out = img.copy()
    for k, (stops, amt) in GRADES.items():
        m = cls == k
        if not m.any():
            continue
        lo, hi = np.percentile(lum[m], [1, 99.5])
        ln = np.clip((lum - lo) / (hi - lo + 1e-6), 0, 1)
        gm = gradient_map(ln, stops)
        out[m] = (amt * gm + (1 - amt) * img)[m]
    return np.clip(out, 0, 1)


def glyph_atlas():
    chars = [chr(c) for c in range(32, 127)]
    W = 40
    H = 2 * W
    size = W / ADV
    font = ImageFont.truetype(FONT, int(round(size)))
    feats, cov = [], []
    for ch in chars:
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        d.text((0, BASELINE * H), ch, fill=255, font=font, anchor="ls")
        a = np.asarray(im, np.float32) / 255
        f = cv2.resize(a, (GX, GY), interpolation=cv2.INTER_AREA)
        feats.append(f.ravel())
        cov.append(a.mean())
    return chars, np.array(feats), np.array(cov)


def in_rects(xs, ys, rects):
    m = np.zeros(xs.shape, bool)
    for x0, y0, x1, y1 in rects:
        m |= (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)
    return m


def convert_level(img, graded, cls, cols, atlas, cfg):
    chars, feats, gcov = atlas
    h, w, _ = img.shape
    cw = w / cols
    rows = int(round(h / (2 * cw)))
    ch = h / rows
    # luminance with local contrast enhancement, sampled at GX x GY per cell
    lum = 0.299 * graded[..., 0] + 0.587 * graded[..., 1] + 0.114 * graded[..., 2]
    blur = cv2.GaussianBlur(lum, (0, 0), 1.6)
    le = np.clip(lum + DETAIL * (lum - blur), 0, 1)
    SW, SH = cols * GX, rows * GY
    interp = cv2.INTER_AREA if SW < w else cv2.INTER_CUBIC
    sub = cv2.resize(le, (SW, SH), interpolation=interp)
    skyf = cv2.resize((cls == SKY).astype(np.float32), (SW, SH), interpolation=cv2.INTER_AREA)
    sub = sub.reshape(rows, GY, cols, GX).transpose(0, 2, 1, 3).reshape(rows, cols, GX * GY)
    skyf = skyf.reshape(rows, GY, cols, GX).transpose(0, 2, 1, 3).reshape(rows, cols, GX * GY)

    # cell-level class: majority vote over non-sky pixels; sky if mostly sky
    frac = np.stack([cv2.resize((cls == k).astype(np.float32), (cols, rows), interpolation=cv2.INTER_AREA)
                     for k in range(6)], -1)
    sky_frac = frac[..., SKY]
    land = frac.copy()
    land[..., SKY] = 0
    ccls = land.argmax(-1)
    ccls[sky_frac >= 0.62] = SKY
    ccls[ccls == OTH] = VEG

    # cell color: mean graded color over non-sky pixels
    nonsky = (cls != SKY).astype(np.float32)[..., None]
    num = cv2.resize(graded * nonsky, (cols, rows), interpolation=cv2.INTER_AREA)
    den = cv2.resize(nonsky[..., 0], (cols, rows), interpolation=cv2.INTER_AREA)[..., None]
    color = num / np.maximum(den, 1e-4)
    clum = 0.299 * color[..., 0] + 0.587 * color[..., 1] + 0.114 * color[..., 2]

    # glow codes from hand-measured regions + darkness
    ys, xs = np.mgrid[0:rows, 0:cols]
    px, py = (xs + 0.5) * cw, (ys + 0.5) * ch
    glow = np.zeros((rows, cols), np.uint8)
    land_cell = ccls != SKY
    glow[in_rects(px, py, cfg["stained_glass"]) & (clum < 0.42) & land_cell] = 1
    glow[in_rects(px, py, cfg["warm_windows"]) & (clum < 0.38) & land_cell] = 2

    cmax = 0.95 * gcov.max()
    gmean = feats.mean(-1)

    def pick(subv, minink, lo, hi, gamma):
        """Choose the best glyph per cell for a target ink pattern subv (higher = more ink)."""
        cell_mean = subv.mean(-1)
        t = np.clip((cell_mean - lo) / (hi - lo), 0, 1)
        base = 0.02 + (cmax - 0.02) * np.power(t, gamma)
        base = base * CLASS_INK[ccls]
        base = np.maximum(base, minink)
        T = np.clip(base[..., None] + SHAPE * (subv - cell_mean[..., None]), 0, 1)
        T = T * (1 - skyf)                       # sky part of edge cells stays empty
        flat = T.reshape(-1, GX * GY)
        d = ((flat[:, None, :] - feats[None, :, :]) ** 2).sum(-1)
        d += TONE_W * (base.ravel()[:, None] - gmean[None, :]) ** 2
        idx = d.argmin(-1).reshape(rows, cols)
        oc = np.array(chars)[idx]
        oc[ccls == SKY] = " "
        return "".join(oc.ravel())

    minink = np.where(glow > 0, 0.16, 0.0)
    chars_dark = pick(sub, minink, TLO, THI, GAMMA)          # light-on-dark: ink = brightness
    chars_light = pick(1.0 - sub, minink, 0.0, 0.78, 0.9)    # ink-on-paper: ink = darkness

    rgb = (np.clip(color, 0, 1) * 255).astype(np.uint8)
    rgb[ccls == SKY] = 0
    return {
        "cols": cols, "rows": rows,
        "chars": chars_light,
        "charsDark": chars_dark,
        "rgb": base64.b64encode(rgb.tobytes()).decode(),
        "cls": "".join(str(int(c)) for c in ccls.ravel()),
        "glow": "".join(str(int(g)) for g in glow.ravel()),
    }


def preview(level, path, light=True):
    cols, rows = level["cols"], level["rows"]
    W, H = 8, 16
    font = ImageFont.truetype(FONT, int(round(W / ADV)))
    im = Image.new("RGB", (cols * W, rows * H), (245, 240, 230) if light else (14, 16, 30))
    key = "chars" if light else "charsDark"
    d = ImageDraw.Draw(im)
    rgb = np.frombuffer(base64.b64decode(level["rgb"]), np.uint8).reshape(rows, cols, 3)
    for y in range(rows):
        for x in range(cols):
            c = level[key][y * cols + x]
            if level["cls"][y * cols + x] == "0":
                continue
            col = rgb[y, x].astype(float)
            col = np.clip(col * 0.72, 0, 255) if light else np.clip(col * 1.15 + 18, 0, 255)
            d.text((x * W, y * H + BASELINE * H), c, fill=tuple(int(v) for v in col), font=font, anchor="ls")
    im.save(path)


def main():
    src, cfg_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    cfg = json.load(open(cfg_path))
    rgb = np.asarray(Image.open(src).convert("RGB"))
    img = rgb.astype(np.float32) / 255
    cls, _ = segment(rgb, cfg)
    cls[cls == OTH] = VEG
    graded = grade(img, cls)
    atlas = glyph_atlas()
    levels = [convert_level(img, graded, cls, c, atlas, cfg) for c in LEVELS]
    h, w = cls.shape
    data = {
        "w": w, "h": h, "baseline": BASELINE, "adv": ADV,
        "focus": cfg.get("focus_x", 0.5),
        "lamps": [[x / w, y / h] for x, y in cfg["lamps"]],
        "levels": levels,
    }
    json.dump(data, open(out, "w"), separators=(",", ":"))
    if len(sys.argv) > 4:
        preview(levels[-1], sys.argv[4], light=True)
        preview(levels[-1], sys.argv[4].replace(".png", "_dark.png"), light=False)
    print("levels:", [(l["cols"], l["rows"]) for l in levels])


if __name__ == "__main__":
    main()
