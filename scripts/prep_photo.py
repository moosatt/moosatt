"""Prep a portrait for ASCII conversion.

Usage:
  python scripts/prep_photo.py source-photo.jpg                 # plain light backdrop
  python scripts/prep_photo.py new-photo.jpg --full             # whole frame, no cutout
  python scripts/prep_photo.py photo.jpg --full --crop=0.135,0,1,0.83 --subject=0.43,0.52,0.47,0.52   # what this profile uses
  python scripts/prep_photo.py new-photo.jpg --grabcut --crop=0.28,0.18,0.70,0.60
  python scripts/prep_photo.py busy.jpg --rembg                 # needs `pip install rembg`

--crop=l,t,r,b   crop box as fractions of the image (default: centred head+shoulders)
--grabcut        isolate the subject on a busy background with OpenCV GrabCut
--rembg          isolate the subject with rembg (best quality, heavier install)

Steps: crop, isolate the subject, boost local contrast with CLAHE, and
composite onto pure white so the background maps to blank space in the ASCII
ramp. Writes source-prepped.png and source-mask.png.
"""
import sys

import cv2
import numpy as np
from PIL import Image


def grabcut_mask(rgb):
    """Subject mask for a head-and-shoulders crop with a busy background."""
    h, w = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gc = np.full((h, w), cv2.GC_PR_BGD, np.uint8)

    yy, xx = np.mgrid[0:h, 0:w]

    def ell(cx, cy, rx, ry):
        return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1

    gc[ell(w * 0.50, h * 0.48, w * 0.40, h * 0.52)] = cv2.GC_PR_FGD   # head guess
    gc[ell(w * 0.55, h * 1.05, w * 0.50, h * 0.22)] = cv2.GC_PR_FGD   # shoulders / hoodie guess
    gc[ell(w * 0.50, h * 0.48, w * 0.18, h * 0.26)] = cv2.GC_FGD       # face + hair core
    gc[: int(h * 0.80), int(w * 0.87):] = cv2.GC_BGD                    # wall behind the ear
    gc[: int(h * 0.60), : int(w * 0.10)] = cv2.GC_BGD                   # dark panel, upper left
    gc[: int(h * 0.04), :] = cv2.GC_BGD
    gc[:, -int(w * 0.03):] = cv2.GC_BGD

    bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(bgr, gc, None, bgd, fgd, 10, cv2.GC_INIT_WITH_MASK)
    mask = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros_like(mask)
    if cnts:
        cv2.drawContours(out, [max(cnts, key=cv2.contourArea)], -1, 255, -1)
    return out


def full_frame_tone(rgb, gray, ellipse=None):
    """Whole-frame tone map that favours the subject.

    The subject area is either a soft ellipse you give (--subject=cx,cy,rx,ry as
    fractions of the cropped image: use this when the subject and background are
    similar in tone) or, by default, found with GrabCut inside a head-centred
    window. Strong local contrast goes on the subject, a gentler treatment on the
    background. Also writes source-subject.png, a soft 0..255 subject mask that
    make_ascii_svg.py uses to dim the background.
    """
    h, w = gray.shape
    if ellipse:
        cx, cy, rx, ry = ellipse
        yy, xx = np.mgrid[0:h, 0:w]
        sub = ((((xx - cx * w) / (rx * w)) ** 2 + ((yy - cy * h) / (ry * h)) ** 2) <= 1).astype(np.uint8) * 255
        soft = cv2.GaussianBlur(sub, (0, 0), 0.07 * w).astype(np.float32) / 255.0
    else:
        x0, y0, x1, y1 = int(w * 0.28), int(h * 0.18), int(w * 0.70), int(h * 0.60)
        sub = np.zeros((h, w), np.uint8)
        sub[y0:y1, x0:x1] = grabcut_mask(rgb[y0:y1, x0:x1])
        sub = cv2.dilate(sub, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
        soft = cv2.GaussianBlur(sub, (0, 0), 28).astype(np.float32) / 255.0
    Image.fromarray((soft * 255).astype(np.uint8)).save("source-subject.png")

    smooth = cv2.bilateralFilter(gray, 9, 40, 9)
    bg = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(smooth)
    fg = cv2.createCLAHE(clipLimit=6.0, tileGridSize=(4, 4)).apply(smooth)
    return (soft * fg + (1 - soft) * bg).astype(np.uint8)


def prep(src, dst="source-prepped.png", mode="plain", crop=None, ellipse=None):
    img = Image.open(src).convert("RGB")
    w, h = img.size

    if crop:
        l, t, r, b = crop
        img = img.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    elif mode == "full":
        pass  # keep the whole frame, no crop
    else:
        box_w = int(w * 0.80)
        left = (w - box_w) // 2
        img = img.crop((left, int(h * 0.05), left + box_w, int(h * 0.88)))

    rgb = np.array(img)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    if mode == "full":
        mask = np.full(gray.shape, 255, np.uint8)
    elif mode == "rembg":
        from rembg import remove

        cut = np.array(remove(img))
        mask = (cut[:, :, 3] > 128).astype(np.uint8) * 255
    elif mode == "grabcut":
        mask = grabcut_mask(rgb)
    else:
        # Plain studio backdrop: anything much brighter than the subject's
        # own tones is background.
        mask = (gray < 238).astype(np.uint8) * 255
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros_like(mask)
        if cnts:
            cv2.drawContours(mask, [max(cnts, key=cv2.contourArea)], -1, 255, -1)

    if mode == "full":
        gray = full_frame_tone(rgb, gray, ellipse)
    else:
        # Smooth skin texture (acne, pores) without blurring real edges, then
        # push local contrast hard so flat lighting still yields features.
        gray = cv2.bilateralFilter(gray, 9, 40, 9)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(6, 6))
        gray = clahe.apply(gray)

    out = np.where(mask > 0, gray, 255).astype(np.uint8)
    Image.fromarray(out).save(dst)
    Image.fromarray(mask).save("source-mask.png")
    print(f"wrote {dst} {out.shape[::-1]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    crop = None
    ellipse = None
    for a in sys.argv[1:]:
        if a.startswith("--crop="):
            crop = tuple(float(v) for v in a.split("=")[1].split(","))
        if a.startswith("--subject="):
            ellipse = tuple(float(v) for v in a.split("=")[1].split(","))
    mode = "rembg" if "--rembg" in sys.argv else "grabcut" if "--grabcut" in sys.argv else "full" if "--full" in sys.argv else "plain"
    prep(args[0] if args else "source-photo.jpg", mode=mode, crop=crop, ellipse=ellipse)
