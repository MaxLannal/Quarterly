"""Pixel-level segmentation of the Rockefeller Chapel photo into scene classes.

Classes: 0 sky, 1 building, 2 foliage, 3 grass, 4 path, 5 other (posts, cars, distant buildings)
"""
import sys
import numpy as np
import cv2
from scipy import ndimage as ndi

SKY, BLD, VEG, GRS, PTH, OTH = range(6)

def segment(rgb, cfg):
    """cfg: dict loaded from a *.regions.json file (hand-measured, photo-specific)."""
    h, w, _ = rgb.shape
    img = rgb.astype(np.float32) / 255.0
    sm = cv2.GaussianBlur(img, (0, 0), 1.2)
    r, g, b = sm[..., 0], sm[..., 1], sm[..., 2]
    hsv = cv2.cvtColor((sm * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    H, S, V = hsv[..., 0], hsv[..., 1] / 255, hsv[..., 2] / 255

    # sky: saturated blue, connected to the top edge
    blue = (H > 95) & (H < 120) & (S > 0.28) & (V > 0.45) & (b > r + 0.15)
    blue = cv2.morphologyEx(blue.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    lab, n = ndi.label(blue)
    keep = set(np.unique(lab[:3, :])) | set(np.unique(lab[:, -3:][:300]))
    keep.discard(0)
    sky = np.isin(lab, list(keep))
    # absorb small non-sky islands fully inside sky (watermark strokes over sky)
    nonsky_lab, m = ndi.label(~sky)
    sizes = ndi.sum(np.ones_like(nonsky_lab), nonsky_lab, range(1, m + 1))
    for i, s in enumerate(sizes, start=1):
        if s < 600:
            sky[nonsky_lab == i] = True

    green = (g > r + 0.012) & (g > b + 0.004)
    yy, xx = np.mgrid[0:h, 0:w]

    cls = np.full((h, w), OTH, np.uint8)
    x0, y0, x1, y1 = cfg["building_box"]
    solid_y, ground_y = cfg["building_solid_above_y"], cfg["ground_y"]
    inbox = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
    cls[~inbox & (yy < ground_y + 6)] = VEG
    cls[inbox & ~green] = BLD
    cls[inbox & green & (yy >= solid_y)] = VEG
    cls[inbox & (yy < solid_y)] = BLD

    lum = 0.299 * r + 0.587 * g + 0.114 * b
    ground = yy >= ground_y
    grass = ground & green & (V > 0.28) & (S > 0.35)
    path = (yy >= ground_y + 6) & (S < 0.3) & ~green & (xx > cfg["path_min_x"])
    cls[grass] = GRS
    cls[path] = PTH
    # lawn far below the hedges is always grass/path
    low = yy > cfg["lawn_y"]
    cls[low & ~path] = GRS
    cls[sky] = SKY
    return cls, sky


if __name__ == "__main__":
    # Debug view: python3 segment.py photo.jpg regions.json  -> seg.png
    import json
    from PIL import Image
    rgb = np.asarray(Image.open(sys.argv[1]).convert("RGB"))
    cls, _ = segment(rgb, json.load(open(sys.argv[2])))
    pal = np.array([[90, 160, 230], [230, 200, 150], [40, 120, 50], [150, 220, 80], [130, 130, 140], [200, 60, 200]], np.uint8)
    vis = (0.55 * pal[cls] + 0.45 * rgb).astype(np.uint8)
    h, w = cls.shape
    Image.fromarray(vis).resize((w * 2, h * 2), Image.NEAREST).save("seg.png")
    for k, name in enumerate(["sky", "building", "foliage", "grass", "path", "other"]):
        print(name, round(float((cls == k).mean()), 3))
