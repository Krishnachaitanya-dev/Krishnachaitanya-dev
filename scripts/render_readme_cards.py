"""Render the animated SVG cards in my profile README.

Reads data/contributions.json (refreshed daily by the Action), data/portrait.txt
(made once by make_portrait.py) and the subset fonts plus glyph widths in fonts/,
then writes cards/*.svg. Standard library only.

The cards are shown through <img>, so they use only what works there: an inline
<style> with CSS keyframes, SMIL <set>/<animateTransform>, and fonts embedded as
base64 WOFF2. Every animation switches off under prefers-reduced-motion.

STATIC=1 renders the final frame with no animation (for screenshots).
CARDS_OUT=dir writes somewhere other than cards/.
"""
import base64
import collections
import datetime as dt
import html
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(os.environ.get("CARDS_OUT", ROOT / "cards"))
STATIC = os.environ.get("STATIC") == "1"

PAPER, INK, INK2, GREY, GREY2 = "#f3f3f1", "#111111", "#3a3a3c", "#6e6e73", "#8e8e93"
RULE, EMPTY, PARTIAL = "#dcdcd7", "#e2e2de", "#c9c9c4"
BLUE, RED, YELLOW, WHITE = "#2f55ff", "#ef3b2d", "#ffc81a", "#ffffff"
TITLE_DARK = "#e6edf3"
HEAT = [EMPTY, "#c8d3ff", "#94a8ff", "#6280ff", BLUE, "#1a3be0"]
EASE = "cubic-bezier(.2,.8,.2,1)"
W, THIRD = 880, 880 / 3

# Each card starts after the one above it, so the page plays top to bottom.
T_HERO, T_HEAT, T_ACT, T_TILES, T_TITLE, T_PROJ = 0.0, 0.8, 1.9, 3.4, 4.4, 4.6

FACES = {
    "serif-400": ("Instrument Serif", "normal", 400),
    "serif-italic": ("Instrument Serif", "italic", 400),
    "geist-400": ("Geist", "normal", 400),
    "geist-600": ("Geist", "normal", 600),
    "geistmono-400": ("Geist Mono", "normal", 400),
}
METRICS = json.loads((ROOT / "fonts" / "metrics.json").read_text())

KEYFRAMES = """
@keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%{opacity:0;transform:scale(0)}70%{opacity:1;transform:scale(1.2)}100%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes swing{0%{opacity:0;transform:translateY(80px) rotate(7deg)}55%{opacity:1;transform:translateY(-9px) rotate(-1.8deg)}78%{transform:translateY(3px) rotate(.5deg)}100%{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes ring{0%{opacity:.7;transform:scale(.2)}100%{opacity:0;transform:scale(1.6)}}
@keyframes nudge{0%,100%{transform:translateX(0)}50%{transform:translateX(4px)}}
@keyframes sweep{0%{transform:translateX(-260px)}45%,100%{transform:translateX(420px)}}
@keyframes appear{from{opacity:0}to{opacity:1}}
.fb{transform-box:fill-box;transform-origin:center}
.fbb{transform-box:fill-box;transform-origin:50% 100%}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.cf,.fx{display:none}}
"""
CLASSES = (
    ".sr{font-family:'Instrument Serif',Georgia,serif}.it{font-style:italic}"
    ".ss{font-family:Geist,system-ui,-apple-system,sans-serif}.b6{font-weight:600}"
    ".mo{font-family:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace}"
)


# ---------------------------------------------------------------- helpers


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def width(text: str, face: str, size: float) -> float:
    m = METRICS[face]
    return sum(m.get(c, 0.55) for c in text) * size


def wrap(text: str, face: str, size: float, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and width(trial, face, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def anim(name: str, dur: float, delay: float, ease: str = EASE) -> str:
    """Inline one-shot animation style, or nothing in STATIC mode."""
    return "" if STATIC else f' style="animation:{name} {dur}s {ease} {delay:.2f}s both"'


def loop(name: str, dur: float, delay: float, ease: str = "ease-in-out") -> str:
    """Inline infinite animation style, or nothing in STATIC mode."""
    return "" if STATIC else f' style="animation:{name} {dur}s {ease} {delay:.2f}s infinite"'


def svg(w: float, h: float, title: str, body: str, faces, extra_css: str = "") -> str:
    css = []
    for key in faces:
        family, style, weight = FACES[key]
        b64 = base64.b64encode((ROOT / "fonts" / f"{key}.woff2").read_bytes()).decode()
        css.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    style = "".join(css) + CLASSES + ("" if STATIC else KEYFRAMES + extra_css)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}" height="{h}" viewBox="0 0 {w:.3f} {h}" '
        f'role="img" aria-labelledby="t"><title id="t">{esc(title)}</title><style>{style}</style>{body}</svg>\n'
    )


def fmt_date(d: dt.date, year: bool = True) -> str:
    return f"{d.day} {d.strftime('%b')}" + (f" {d.year}" if year else "")


# ---------------------------------------------------------------- data


def load_stats() -> dict:
    data = json.loads((ROOT / "data" / "contributions.json").read_text())
    days = [(dt.date.fromisoformat(d["date"]), d["count"]) for d in data["days"]]
    counts = [c for _, c in days]

    i = len(days) - 1
    if counts[i] == 0:  # today may still be empty
        i -= 1
    current = 0
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1

    longest, run, start, longest_range = 0, 0, None, (None, None)
    for d, c in days:
        if c > 0:
            start = d if run == 0 else start
            run += 1
            if run > longest:
                longest, longest_range = run, (start, d)
        else:
            run = 0

    busiest_day, busiest = max(days, key=lambda x: x[1])
    months = collections.OrderedDict()
    for d, c in days:
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    nonzero = sorted(c for c in counts if c > 0) or [1]
    return {
        "fetched": dt.date.fromisoformat(data["fetched"]),
        "days": days,
        "active": sum(1 for c in counts if c > 0),
        "current": current,
        "longest": longest,
        "longest_range": longest_range,
        "busiest": busiest,
        "busiest_day": busiest_day,
        "months": list(months.items())[-12:],
        "cuts": [nonzero[int(len(nonzero) * p)] for p in (0.2, 0.4, 0.6, 0.8)],
    }


# ---------------------------------------------------------------- cards


def hero() -> str:
    H = 432
    name1, name2 = "Krishna", "Chaitanya"
    size = min(116, 470 / max(width(name1, "serif-400", 1), width(name2, "serif-italic", 1)))
    desc = "I turn business requirements into web, mobile and SaaS products that ship."
    lines = wrap(desc, "geist-400", 18, 450)
    link = "linkedin.com/in/krishnachaitanyadoppa"

    shine_defs, shine_text = "", ""
    if not STATIC:
        shine_defs = (
            f'<defs><linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="160" y2="0">'
            f'<stop offset="0" stop-color="{BLUE}" stop-opacity="0"/><stop offset=".5" stop-color="{BLUE}"/>'
            f'<stop offset="1" stop-color="{BLUE}" stop-opacity="0"/>'
            f'<animateTransform attributeName="gradientTransform" type="translate" values="-200 0;600 0;600 0" '
            f'keyTimes="0;.45;1" dur="5s" begin="{T_HERO + 1.6}s" repeatCount="indefinite"/></linearGradient></defs>'
        )
        shine_text = f'<text class="sr it fx" x="44" y="262" font-size="{size:.1f}" fill="url(#shine)">{name2}</text>'

    rows = (ROOT / "data" / "portrait.txt").read_text().rstrip("\n").split("\n")
    cols = max(map(len, rows))
    box_x, box_y, box_w, box_h = 516, 26, 336, 388
    fs = box_w / cols / METRICS["geistmono-400"]["a"]
    lh = fs * 0.9
    top = box_y + max(0, (box_h - len(rows) * lh) / 2) + fs * 0.8
    art = "".join(
        f'<text class="mo" x="{box_x}" y="{top + i * lh:.2f}" font-size="{fs:.3f}" fill="{INK}" '
        f'xml:space="preserve"{anim("fade", 0.35, T_HERO + 0.4 + i * 0.018)}>{esc(r)}</text>'
        for i, r in enumerate(rows)
    )

    link_y = 318 + len(lines) * 25 + 20
    body = (
        f'<rect width="{W}" height="{H - 12}" rx="14" fill="{PAPER}"/>'
        + shine_defs
        + f'<rect x="48" y="49" width="8" height="8" rx="2" fill="{BLUE}"{loop("pulse", 2.2, T_HERO + 1.2)}/>'
        + f'<text class="mo" x="64" y="57" font-size="12" letter-spacing="1.2" fill="{INK2}"{anim("fade", 0.6, T_HERO)}>'
        f"SENIOR PROJECT MANAGER AT THE BUSINESS WINGS</text>"
        + f'<text class="sr" x="44" y="166" font-size="{size:.1f}" fill="{INK}"{anim("rise", 0.9, T_HERO + 0.15)}>{name1}</text>'
        + f'<g{anim("rise", 0.9, T_HERO + 0.3)}><text class="sr it" x="44" y="262" font-size="{size:.1f}" fill="{INK}">{name2}</text>'
        f"{shine_text}</g>"
        + f'<g{anim("rise", 0.8, T_HERO + 0.5)}>'
        + "".join(
            f'<text class="ss" x="48" y="{318 + k * 25}" font-size="18" fill="{INK2}">{esc(t)}</text>'
            for k, t in enumerate(lines)
        )
        + "</g>"
        + f'<g{anim("fade", 0.6, T_HERO + 0.75)}><text class="mo" x="48" y="{link_y}" font-size="13" fill="{INK}">{link}</text>'
        f'<text class="ss" x="{48 + width(link, "geistmono-400", 13) + 8:.1f}" y="{link_y}" font-size="13" fill="{BLUE}">↗</text></g>'
        + art
    )
    return svg(W, H, "Krishna Chaitanya Doppa, Senior Project Manager at The Business Wings. " + desc, body,
               ["serif-400", "serif-italic", "geist-400", "geistmono-400"])


def heatmap(s: dict) -> str:
    H = 257
    days = s["days"]
    offset = (days[0][0].weekday() + 1) % 7  # Sunday is row 0
    n_weeks = (offset + len(days) + 6) // 7
    x0, y0, step, cell = 44, 96, 15, 12
    cells, labels, seen = [], [], set()
    LEGEND_X = W - 44 - width("more", "geistmono-400", 11) - 6 - len(HEAT) * step - 6 - width("less", "geistmono-400", 11)
    for i, (d, c) in enumerate(days):
        wk, dow = divmod(offset + i, 7)
        lvl = 0 if c == 0 else 1 + sum(c > x for x in s["cuts"])
        cells.append(
            f'<rect class="fb" x="{x0 + wk * step}" y="{y0 + dow * step}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{HEAT[lvl]}"{anim("pop", 0.4, T_HEAT + 0.2 + wk * 0.02 + dow * 0.012)}/>'
        )
        key = (d.year, d.month)
        if d.day <= 7 and dow == 0 and key not in seen and 0 < wk and x0 + wk * step < LEGEND_X - 50:
            seen.add(key)
            labels.append(
                f'<text class="mo" x="{x0 + wk * step}" y="{y0 + 7 * step + 21}" font-size="11" fill="{GREY}">'
                f'{d.strftime("%b")}</text>'
            )
    ly = y0 + 7 * step + 21
    lx = W - 44 - width("more", "geistmono-400", 11) - 6 - len(HEAT) * step
    legend = (
        f'<text class="mo" x="{lx - 6:.1f}" y="{ly}" font-size="11" fill="{GREY}" text-anchor="end">less</text>'
        + "".join(
            f'<rect x="{lx + k * step:.1f}" y="{ly - 10}" width="{cell - 2}" height="{cell - 2}" rx="2.5" fill="{c}"/>'
            for k, c in enumerate(HEAT)
        )
        + f'<text class="mo" x="{W - 44}" y="{ly}" font-size="11" fill="{GREY}" text-anchor="end">more</text>'
    )
    body = (
        f'<rect width="{W}" height="{H - 12}" rx="14" fill="{PAPER}"/>'
        f'<text class="sr" x="42" y="62" font-size="34" fill="{INK}"{anim("rise", 0.8, T_HEAT)}>'
        f'My year, <tspan class="it" fill="{BLUE}">in blue</tspan></text>'
        f'<text class="mo" x="{W - 44}" y="60" font-size="12" letter-spacing="1.2" fill="{GREY}" text-anchor="end"'
        f'{anim("fade", 0.6, T_HEAT)}>MOSTLY PRIVATE CLIENT REPOS · REFRESHED DAILY</text>'
        + "".join(cells) + "".join(labels) + legend
    )
    return svg(W, H, "My contribution graph for the last year, in blue, refreshed daily", body,
               ["serif-400", "serif-italic", "geistmono-400"])


def activity(s: dict) -> str:
    H = 352
    months = s["months"]
    total = sum(c for _, c in months)
    top = max(c for _, c in months) or 1
    best = max(range(len(months)), key=lambda i: months[i][1])
    current_month = (s["fetched"].year, s["fetched"].month)
    left, slot, bw, base, max_h = 40, 47.5, 37.5, 292, 140
    bars = []
    for i, ((y, m), c) in enumerate(months):
        h = max(4, c / top * max_h)
        x = left + i * slot
        fill = BLUE if i == best else PARTIAL if (y, m) == current_month else INK
        d = T_ACT + 0.3 + i * 0.07
        bars.append(
            f'<rect class="fbb" x="{x:.1f}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" rx="4" fill="{fill}"'
            f'{anim("grow", 0.7, d)}/>'
            f'<text class="mo" x="{x + bw / 2:.1f}" y="{base + 22}" font-size="11" fill="{GREY}" text-anchor="middle"'
            f'{anim("fade", 0.5, d)}>{dt.date(y, m, 1).strftime("%b")}</text>'
        )
    bh = max(4, months[best][1] / top * max_h)
    bars.append(
        f'<text class="mo fb" x="{left + best * slot + bw / 2:.1f}" y="{base - bh - 10:.1f}" font-size="11" fill="{BLUE}" '
        f'text-anchor="middle"{anim("pop", 0.45, T_ACT + 0.3 + len(months) * 0.07 + 0.3)}>{months[best][1]:,}</text>'
    )

    if s["current"] >= 3:
        streak_n = s["current"]
        streak_label = "current streak" + (", and the longest" if s["current"] >= s["longest"] else "")
    else:
        streak_n = s["longest"]
        a, b = s["longest_range"]
        streak_label = f"longest streak, {fmt_date(a, False)} – {fmt_date(b, False)}"
    stats = [
        (f'{streak_n} <tspan class="it">days</tspan>', streak_label),
        (f'{s["active"]}<tspan fill="{GREY2}"> / {len(s["days"])}</tspan>', "days with a commit"),
        (f'{s["busiest"]:,}', f'on the busiest day, {fmt_date(s["busiest_day"])}'),
    ]
    right = []
    for k, (num, label) in enumerate(stats):
        y = 112 + k * 92
        right.append(
            f'<g{anim("rise", 0.7, T_ACT + 0.5 + k * 0.15)}>'
            f'<text class="sr" x="640" y="{y}" font-size="40" fill="{INK}">{num}</text>'
            f'<text class="ss" x="641" y="{y + 22}" font-size="13" fill="{GREY}">{esc(label)}</text></g>'
        )
        if k < 2:
            right.append(f'<path d="M640 {y + 44}H840" stroke="{RULE}"{anim("fade", 0.6, T_ACT + 0.6 + k * 0.15)}/>')
    body = (
        f'<rect width="{W}" height="{H - 12}" rx="14" fill="{PAPER}"/>'
        f'<text class="mo" x="40" y="58" font-size="12" letter-spacing="1" fill="{GREY}"{anim("fade", 0.6, T_ACT)}>'
        f"THE LAST 12 MONTHS ON GITHUB</text>"
        f'<text class="sr" x="38" y="114" font-size="52" fill="{INK}"{anim("rise", 0.8, T_ACT + 0.1)}>'
        f'{total:,} <tspan class="it">contributions</tspan></text>'
        + "".join(bars) + "".join(right)
    )
    return svg(W, H, f"{total:,} contributions in the last 12 months, by month, with streak and busiest day", body,
               ["serif-400", "serif-italic", "geist-400", "geistmono-400"])


def tile(i: int, label: str, target: int, final: str, unit: str, desc: str, color: str, fg: str) -> str:
    H, tw, th = 222, THIRD - 8, 210
    t0 = T_TILES + i * 0.25
    t_count, frames, frame_dt = t0 + 0.6, 18, 0.045
    size = min(44, 236 / (width(final, "serif-400", 1) + width(" " + unit, "serif-italic", 1)))

    def big(value: str, cls: str, extra: str, inner: str = "") -> str:
        return (f'<text class="sr{cls}" x="22" y="112" font-size="{size:.1f}" fill="{fg}"{extra}>'
                f'{esc(value)}<tspan class="it"> {esc(unit)}</tspan>{inner}</text>')

    count = ""
    if not STATIC:
        for f in range(1, frames):
            v = round(target * (1 - (1 - f / frames) ** 3))
            count += big(
                f"{v:,}", " cf", ' visibility="hidden"',
                f'<set attributeName="visibility" to="visible" begin="{t_count + f * frame_dt:.3f}s" dur="{frame_dt}s"/>',
            )
    final_el = big(final, "", "" if STATIC else f' style="animation:appear .01s linear {t_count + frames * frame_dt:.3f}s both"')

    lines = wrap(desc, "geist-400", 13.5, 238)
    fx = ""
    if not STATIC:
        fx = (
            f'<circle class="fx fb" cx="{tw - 40:.1f}" cy="170" r="60" fill="none" stroke="{fg}" stroke-opacity=".5" '
            f'stroke-width="2"{loop("ring", 3.2, t0 + 1.2, "ease-out")}/>'
            f'<rect class="fx" x="0" y="-20" width="90" height="{th + 40}" fill="url(#gl)"'
            f'{loop("sweep", 5.5, t0 + 2.0)}/>'
        )
    body = (
        f'<defs><clipPath id="c"><rect width="{tw:.3f}" height="{th}" rx="14"/></clipPath>'
        f'<linearGradient id="gl" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="#fff" stop-opacity=".28"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        f"</linearGradient></defs>"
        f'<g class="fbb"{anim("swing", 1.0, t0)}><g clip-path="url(#c)">'
        f'<rect width="{tw:.3f}" height="{th}" fill="{color}"/>{fx}</g>'
        f'<text class="mo" x="24" y="38" font-size="12" letter-spacing="1.2" fill="{fg}">{label}</text>'
        f'<text class="ss fb" x="{tw - 36:.1f}" y="38" font-size="14" fill="{fg}"{loop("nudge", 1.6, t0 + 1.0)}>→</text>'
        + count + final_el
        + "".join(
            f'<text class="ss" x="24" y="{150 + k * 18}" font-size="13.5" fill="{fg}" fill-opacity=".92">{esc(t)}</text>'
            for k, t in enumerate(lines)
        )
        + "</g>"
    )
    return svg(THIRD, H, f"{label}: {final} {unit}. {desc}", body,
               ["serif-400", "serif-italic", "geist-400", "geistmono-400"])


def title(dark: bool) -> str:
    body = (
        f'<text class="sr" x="2" y="46" font-size="34" fill="{TITLE_DARK if dark else INK}"'
        f'{anim("rise", 0.8, T_TITLE)}>What I’ve <tspan class="it">shipped</tspan></text>'
    )
    return svg(W, 64, "What I've shipped", body, ["serif-400", "serif-italic"])


def project(i: int, name: str, desc: str, footer: str, color: str) -> str:
    H, tw = 188, THIRD - 8
    lines = wrap(desc, "geist-400", 14, tw - 48)[:3]
    body = (
        f'<g{anim("rise", 0.8, T_PROJ + i * 0.15)}>'
        f'<rect width="{tw:.3f}" height="{H - 12}" rx="14" fill="{PAPER}"/>'
        f'<rect x="24" y="30" width="8" height="8" rx="2" fill="{color}"/>'
        f'<text class="ss b6" x="40" y="39" font-size="18" fill="{INK}">{esc(name)}</text>'
        + "".join(
            f'<text class="ss" x="24" y="{72 + k * 21}" font-size="14" fill="{INK2}">{esc(t)}</text>'
            for k, t in enumerate(lines)
        )
        + f'<text class="mo" x="24" y="152" font-size="12" fill="{GREY}">{esc(footer)}</text></g>'
    )
    return svg(THIRD, H, f"{name}: {desc}", body, ["geist-400", "geist-600", "geistmono-400"])


TILES = [
    ("plan", "PLAN", 15, "15", "requirements",
     "Traced to evidence in one audit, for an electronics retailer's price catalogue.", BLUE, WHITE),
    ("ship", "SHIP", 2, "2", "app stores",
     "Advance Washing, live on Google Play and the App Store, built end to end.", RED, WHITE),
    ("lead", "LEAD", 4, "4–5", "people",
     "Led the AISMARTLIVE team that built Alankara AI, a virtual try-on.", YELLOW, INK),
]
PROJECTS = [
    ("advance-washing", "Advance Washing",
     "Laundry pickup and delivery in Mumbai, with WhatsApp ordering. Live on both app stores.",
     "Supabase · live", BLUE),
    ("enorbit", "EnOrbit",
     "I built and run the platform behind EnOrbit, a WhatsApp automation SaaS sold by EnValues.",
     "Supabase · live", RED),
    ("price-catalogue", "Price catalogue",
     "A 3,104-product price catalogue for an electronics retailer, built from one client meeting.",
     "Supabase · 237 tests", YELLOW),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = load_stats()
    cards = {
        "hero": hero(),
        "heatmap": heatmap(s),
        "activity": activity(s),
        "title-shipped-light": title(False),
        "title-shipped-dark": title(True),
    }
    for i, (slug, *args) in enumerate(TILES):
        cards[slug] = tile(i, *args)
    for i, (slug, *args) in enumerate(PROJECTS):
        cards[f"project-{slug}"] = project(i, *args)
    for name, content in cards.items():
        (OUT / f"{name}.svg").write_text(content)
        print(f"{name}.svg {len(content) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
