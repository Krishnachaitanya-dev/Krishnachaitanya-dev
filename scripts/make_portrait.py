"""Turn a portrait (photo or illustration on a plain background) into the ASCII art used by the hero card.

Run locally once (needs Pillow, NumPy and OpenCV); it writes data/portrait.txt,
which the daily card renderer reads. The source image itself is not committed.

    python scripts/make_portrait.py path/to/photo.jpg [--cols 132] [--preview out.png]
"""
import argparse
import pathlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
# light -> dark; dark pixels get dense glyphs because the card prints ink on paper
RAMP = " .:-=+*#%@"
WHITE, BLACK, GAMMA = 226.0, 30.0, 1.7  # levels: background and highlights blank, eyes and hair darkest
DETAIL = 1.1  # local contrast boost after downsampling, keeps eyes apart from brows
FLOOR = 0.03  # faint fill inside the figure so skin and shirt keep their shape
CHAR_ASPECT = 0.6 / 0.9  # Geist Mono advance / line height used by render_readme_cards.py
CROP = (0.10, 0.04, 0.90, 0.90)  # head and shoulders, as fractions of the image
FADE = 0.12  # bottom share of rows that fades out
SIDE_FADE = 0.08  # share of columns on each side that fades out


def cut_out(img: np.ndarray) -> np.ndarray:
    """Foreground mask: everything that differs in colour from the plain background."""
    h, w = img.shape[:2]
    corners = np.concatenate([img[:40, :40], img[:40, -40:], img[-40:, :40], img[-40:, -40:]]).reshape(-1, 3)
    bg = np.median(corners, axis=0)
    dist = np.linalg.norm(img.astype(np.float32) - bg, axis=2)
    fg = (dist > 28).astype(np.uint8) * 255
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n > 1:  # keep the person, drop paper texture specks
        fg = np.where(labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]), 255, 0).astype(np.uint8)
    return cv2.GaussianBlur(fg, (11, 11), 0)


def to_ascii(path: str, cols: int) -> list[str]:
    bgr = cv2.imread(path)
    alpha = cut_out(bgr).astype(np.float32) / 255.0
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    tone = np.clip((WHITE - gray) / (WHITE - BLACK), 0, 1) ** GAMMA
    ink = np.maximum(tone, FLOOR) * alpha  # background stays blank paper

    h, w = ink.shape
    x0, y0, x1, y1 = (int(CROP[0] * w), int(CROP[1] * h), int(CROP[2] * w), int(CROP[3] * h))
    ink = ink[y0:y1, x0:x1]
    h, w = ink.shape
    rows = round(cols * (h / w) * CHAR_ASPECT)
    small = cv2.resize(ink, (cols, rows), interpolation=cv2.INTER_AREA)
    small = small + DETAIL * (small - cv2.GaussianBlur(small, (0, 0), 1.4))
    fade_rows = int(rows * FADE)
    if fade_rows:
        small[-fade_rows:] *= np.linspace(1, 0, fade_rows)[:, None]
    edge = max(1, int(cols * SIDE_FADE))
    ramp = np.minimum(1, np.minimum(np.arange(cols), np.arange(cols)[::-1]) / edge)
    small *= ramp[None, :]  # shoulders fade out instead of ending at a hard edge
    idx = (np.clip(small, 0, 1) * (len(RAMP) - 1)).round().astype(int)
    lines = ["".join(RAMP[i] for i in row).rstrip() for row in idx]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def preview(lines: list[str], out: str) -> None:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
    cw, lh = 6.0, 9.0
    width = int(max(map(len, lines)) * cw) + 20
    im = Image.new("RGB", (width, int(len(lines) * lh) + 20), "#f3f3f1")
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        d.text((10, 10 + i * lh), line, fill="#111111", font=font)
    im.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--cols", type=int, default=132)
    ap.add_argument("--preview")
    a = ap.parse_args()
    art = to_ascii(a.photo, a.cols)
    (ROOT / "data" / "portrait.txt").write_text("\n".join(art) + "\n")
    print(f"{len(art)} rows x {max(map(len, art))} cols -> data/portrait.txt")
    if a.preview:
        preview(art, a.preview)
