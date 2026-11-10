"""Turn a portrait photo into the ASCII art used by the hero card.

Run locally once (needs Pillow, NumPy and OpenCV); it writes data/portrait.txt,
which the daily card renderer reads. The photo itself is not committed.

    python scripts/make_portrait.py path/to/photo.jpg [--cols 100] [--preview out.png]
"""
import argparse
import pathlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
# light -> dark; dark pixels get dense glyphs because the card prints ink on paper
RAMP = " .:-=+*#%@"
WHITE, BLACK, GAMMA = 205.0, 25.0, 1.15
CHAR_ASPECT = 0.602 / 0.885  # mono advance / line height used by render_readme_cards.py


def cut_out(img: np.ndarray) -> np.ndarray:
    """Foreground mask via GrabCut seeded with a rectangle around the subject."""
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    rect = (int(w * 0.03), int(h * 0.08), int(w * 0.94), int(h * 0.92))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    return cv2.GaussianBlur(fg, (9, 9), 0)


def to_ascii(path: str, cols: int) -> list[str]:
    bgr = cv2.imread(path)
    alpha = cut_out(bgr).astype(np.float32) / 255.0
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # levels: skin and shirt stay light, hair, beard, brows and eyes go dark
    tone = np.clip((WHITE - gray) / (WHITE - BLACK), 0, 1) ** GAMMA
    edges = cv2.Canny(gray.astype(np.uint8), 30, 90).astype(np.float32) / 255.0
    edges = cv2.GaussianBlur(edges, (0, 0), 2.0) * 2.2
    # faint 0.1 floor keeps the shirt and shoulders as a dotted silhouette
    ink = np.maximum(np.maximum(tone, np.clip(edges, 0, 0.45)), 0.1) * alpha  # background stays blank

    h, w = ink.shape
    rows = round(cols * (h / w) * CHAR_ASPECT)
    small = cv2.resize(ink, (cols, rows), interpolation=cv2.INTER_AREA)
    idx = (np.clip(small, 0, 1) * (len(RAMP) - 1)).round().astype(int)
    lines = ["".join(RAMP[i] for i in row).rstrip() for row in idx]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def preview(lines: list[str], out: str) -> None:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
    cw, lh = 6.02, 8.85
    width = int(max(map(len, lines)) * cw) + 20
    im = Image.new("RGB", (width, int(len(lines) * lh) + 20), "#F4F7F5")
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        d.text((10, 10 + i * lh), line, fill="#0E3B43", font=font)
    im.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--cols", type=int, default=100)
    ap.add_argument("--preview")
    a = ap.parse_args()
    art = to_ascii(a.photo, a.cols)
    (ROOT / "data" / "portrait.txt").write_text("\n".join(art) + "\n")
    print(f"{len(art)} rows x {max(map(len, art))} cols -> data/portrait.txt")
    if a.preview:
        preview(art, a.preview)
