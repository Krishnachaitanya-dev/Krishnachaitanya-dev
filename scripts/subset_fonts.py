"""Subset the card fonts and record glyph widths.

Run locally once (needs fontTools + brotli). Source files are the OFL builds from
@fontsource (Instrument Serif, Geist, Geist Mono). Writes fonts/*.woff2 and
fonts/metrics.json, which the renderer uses to fit text without fontTools.

    python scripts/subset_fonts.py path/to/source-dir
"""
import json
import pathlib
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "·–’→↗★"
FONTS = {
    "serif-400": "instrument-serif-latin-400-normal.woff2",
    "serif-italic": "instrument-serif-latin-400-italic.woff2",
    "geist-400": "geist-sans-latin-400-normal.woff2",
    "geist-600": "geist-sans-latin-600-normal.woff2",
    "geistmono-400": "geist-mono-latin-400-normal.woff2",
}


def main(src: pathlib.Path) -> None:
    metrics = {}
    for name, file in FONTS.items():
        font = TTFont(src / file)
        cmap = font.getBestCmap()
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=[ord(c) for c in CHARS if ord(c) in cmap])
        sub.subset(font)
        font.flavor = "woff2"
        font.save(ROOT / "fonts" / f"{name}.woff2")
        upm = font["head"].unitsPerEm
        hmtx = font["hmtx"]
        cmap = font.getBestCmap()
        metrics[name] = {c: round(hmtx[cmap[ord(c)]][0] / upm, 4) for c in CHARS if ord(c) in cmap}
        print(f"{name}: {len(metrics[name])} glyphs, {(ROOT / 'fonts' / f'{name}.woff2').stat().st_size} bytes")
    (ROOT / "fonts" / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))
