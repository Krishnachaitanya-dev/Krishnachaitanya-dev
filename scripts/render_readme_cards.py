"""Render the animated SVG cards shown in my profile README.

Reads data/contributions.json (refreshed daily by the Action), data/portrait.txt
(made once by make_portrait.py) and the subset fonts in fonts/, and writes cards/*.svg.

The cards are shown through <img>, so they only use what works there: an inline
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

TEAL, LINE, MINT = "#0E3B43", "#1F535B", "#34D399"
WHITE, MUTED, DIM = "#F4F7F5", "#A3BDB9", "#6F948F"
PAPER, INK = "#F4F7F5", "#0E3B43"
GRAPH_LEVELS = ["#174A52", "#1D6A5E", "#23906C", "#2CB57F", MINT]
EASE = "cubic-bezier(.2,.8,.2,1)"

# Cards start one after another so the page plays top to bottom.
T_HERO, T_GRAPH, T_ACTIVITY, T_TILES, T_WORK = 0.0, 1.3, 2.4, 3.2, 3.9

FONTS = {
    "sans700": ("CardSans", 700, "inter-700.woff2"),
    "sans500": ("CardSans", 500, "inter-500.woff2"),
    "mono": ("CardMono", 400, "mono-400.woff2"),
}

KEYFRAMES = """
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%{opacity:0;transform:scale(0)}70%{opacity:1;transform:scale(1.25)}100%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes slidein{from{opacity:0;transform:translateX(-28px)}to{opacity:1;transform:none}}
@keyframes swing{0%{opacity:0;transform:translateY(90px) rotate(8deg)}55%{opacity:1;transform:translateY(-10px) rotate(-2deg)}78%{transform:translateY(4px) rotate(.6deg)}100%{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes ring{0%{opacity:.6;transform:scale(.15)}100%{opacity:0;transform:scale(1)}}
@keyframes nudge{0%,100%{transform:translateX(0)}50%{transform:translateX(5px)}}
@keyframes appear{from{opacity:0}to{opacity:1}}
.fb{transform-box:fill-box;transform-origin:center}
.fbb{transform-box:fill-box;transform-origin:50% 100%}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.cf,.fx{display:none}}
"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def anim(name: str, dur: float, delay: float, ease: str = EASE, tail: str = "both") -> str:
    """Inline animation style, or nothing in STATIC mode."""
    if STATIC:
        return ""
    return f' style="animation:{name} {dur}s {ease} {delay:.3f}s {tail}"'


def font_css(keys) -> str:
    css = []
    for k in keys:
        family, weight, file = FONTS[k]
        b64 = base64.b64encode((ROOT / "fonts" / file).read_bytes()).decode()
        css.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    css.append(
        ".b{font-family:CardSans,Inter,Segoe UI,sans-serif;font-weight:700}"
        ".m{font-family:CardSans,Inter,Segoe UI,sans-serif;font-weight:500}"
        ".mono{font-family:CardMono,DejaVu Sans Mono,Menlo,monospace}"
    )
    return "".join(css)


def svg(w: int, h: int, title: str, body: str, fonts=("sans700", "sans500", "mono"), extra_css: str = "") -> str:
    style = font_css(fonts) + ("" if STATIC else KEYFRAMES + extra_css)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-labelledby="t"><title id="t">{esc(title)}</title>'
        f"<style>{style}</style>{body}</svg>\n"
    )


def frame(w: int, h: int, accent_top: bool = False) -> str:
    """Teal card with the faint blueprint grid from my LinkedIn banner."""
    top = f'<rect width="{w}" height="3" fill="{MINT}"/>' if accent_top else ""
    return (
        f'<defs><clipPath id="card"><rect width="{w}" height="{h}" rx="18"/></clipPath>'
        f'<pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse">'
        f'<path d="M36 0H0V36" fill="none" stroke="{WHITE}" stroke-opacity=".035"/></pattern></defs>'
        f'<g clip-path="url(#card)"><rect width="{w}" height="{h}" fill="{TEAL}"/>'
        f'<rect width="{w}" height="{h}" fill="url(#grid)"/>{top}</g>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="17.5" fill="none" stroke="{LINE}"/>'
    )


def wrap(text: str, max_chars: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


def fmt_date(d: dt.date, year: bool = True) -> str:
    return f"{d.day} {d.strftime('%b')}" + (f" {d.year}" if year else "")


# ---------------------------------------------------------------- data


def load_stats() -> dict:
    data = json.loads((ROOT / "data" / "contributions.json").read_text())
    days = [(dt.date.fromisoformat(d["date"]), d["count"]) for d in data["days"]]
    counts = [c for _, c in days]

    # current streak: today may still be empty, so start from yesterday in that case
    i = len(days) - 1
    if counts[i] == 0:
        i -= 1
    current = 0
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1

    longest, run, run_start, best_range = 0, 0, None, (None, None)
    for d, c in days:
        if c > 0:
            run_start = d if run == 0 else run_start
            run += 1
            if run > longest:
                longest, best_range = run, (run_start, d)
        else:
            run = 0

    busiest_day, busiest = max(days, key=lambda x: x[1])
    months = collections.OrderedDict()
    for d, c in days:
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    last12 = list(months.items())[-12:]

    sums = [sum(counts[i:i + 7]) for i in range(len(counts) - 6)]
    wk = max(range(len(sums)), key=sums.__getitem__)

    nonzero = sorted(c for c in counts if c > 0) or [1]
    q = [nonzero[int(len(nonzero) * p)] for p in (0.25, 0.5, 0.75)]

    return {
        "fetched": dt.date.fromisoformat(data["fetched"]),
        "total": data["total"],
        "days": days,
        "active": sum(1 for c in counts if c > 0),
        "current": current,
        "longest": longest,
        "longest_range": best_range,
        "busiest": busiest,
        "busiest_day": busiest_day,
        "best_week": sums[wk],
        "best_week_start": days[wk][0],
        "months": last12,
        "quartiles": q,
    }


def level(count: int, q: list[int]) -> int:
    if count == 0:
        return 0
    return 1 + sum(count > x for x in q)


# ---------------------------------------------------------------- cards


def hero() -> str:
    W, H = 1000, 470
    rows = (ROOT / "data" / "portrait.txt").read_text().rstrip("\n").split("\n")
    cols = max(map(len, rows))
    px, py, pw, ph = 28, 28, 404, 414  # paper window
    bar = 30
    adv = (pw - 28) / cols
    fs = adv / 0.60205
    lh = fs * 0.885
    art_h = len(rows) * lh
    top = py + bar + (ph - bar - art_h) / 2
    t0, step = T_HERO + 0.35, 0.018
    print_end = t0 + len(rows) * step

    art = []
    for i, row in enumerate(rows):
        y = top + i * lh + fs * 0.78
        art.append(
            f'<text class="mono" x="{px + 14}" y="{y:.2f}" font-size="{fs:.3f}" fill="{INK}" '
            f'xml:space="preserve"{anim("fade", 0.3, t0 + i * step)}>{esc(row)}</text>'
        )
    scan = ""
    if not STATIC:
        scan = (
            f'<rect class="fx" x="{px + 10}" y="{top:.1f}" width="{pw - 20}" height="2.5" rx="1.2" fill="{MINT}" '
            f'style="animation:scan {print_end - t0:.2f}s linear {t0:.2f}s both"/>'
        )
    window = (
        f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="12" fill="{PAPER}"/>'
        f'<path d="M{px} {py + bar}H{px + pw}" stroke="{INK}" stroke-opacity=".12"/>'
        + "".join(
            f'<circle cx="{px + 18 + k * 14}" cy="{py + bar / 2}" r="4.5" fill="{INK}" fill-opacity="{o}"/>'
            for k, o in enumerate((0.55, 0.3, 0.15))
        )
        + f'<text class="mono" x="{px + 64}" y="{py + bar / 2 + 4}" font-size="11" fill="{INK}" fill-opacity=".55">portrait.txt</text>'
        + f'<text class="mono" x="{px + pw - 14}" y="{py + bar / 2 + 4}" font-size="11" fill="{INK}" '
        f'fill-opacity=".4" text-anchor="end">{len(rows)} rows</text>'
        + "".join(art)
        + scan
    )

    x = 468
    shine = ""
    if not STATIC:
        shine = (
            f'<text class="b fx" x="{x}" y="212" font-size="31" letter-spacing="-.8" fill="url(#shine)">'
            f"Technical Project Manager</text>"
        )
    nodes = [("Requirements", 482), ("Build", 636), ("Test", 790), ("Release", 944)]
    rail = (
        f'<path d="M{nodes[0][1]} 404H{nodes[-1][1]}" stroke="{MINT}" stroke-opacity=".55" stroke-width="2" '
        f'pathLength="1" stroke-dasharray="1"{anim("draw", 1.4, T_HERO + 1.1, "ease-in-out")}/>'
    )
    for k, (label, nx) in enumerate(nodes):
        d = T_HERO + 1.1 + k * 0.42
        rail += (
            f'<g class="fb"{anim("pop", 0.45, d)}><circle cx="{nx}" cy="404" r="7" fill="{TEAL}" stroke="{MINT}" stroke-width="2"/>'
            f'<circle cx="{nx}" cy="404" r="2.6" fill="{MINT}"/></g>'
            f'<text class="mono" x="{nx}" y="430" font-size="11.5" fill="{MUTED}" text-anchor="middle"'
            f'{anim("fade", 0.4, d + 0.1)}>{label}</text>'
        )
    if not STATIC:
        rail += (
            f'<circle class="fx" cx="{nodes[0][1]}" cy="404" r="3.5" fill="{WHITE}" '
            f'style="animation:travel 4.5s ease-in-out {T_HERO + 3.2:.1f}s infinite"/>'
        )

    text = (
        f'<text class="b" x="{x}" y="100" font-size="46" letter-spacing="-1.4" fill="{WHITE}"'
        f'{anim("rise", 0.8, T_HERO + 0.15)}>Krishna Chaitanya</text>'
        f'<text class="b" x="{x}" y="152" font-size="46" letter-spacing="-1.4" fill="{WHITE}"'
        f'{anim("rise", 0.8, T_HERO + 0.3)}>Doppa</text>'
        f'<g{anim("rise", 0.8, T_HERO + 0.45)}><text class="b" x="{x}" y="212" font-size="31" letter-spacing="-.8">'
        f'<tspan fill="{MINT}">Technical</tspan><tspan fill="{WHITE}"> Project Manager</tspan></text>{shine}</g>'
        f'<g{anim("rise", 0.8, T_HERO + 0.6)}>'
        f'<text class="m" x="{x}" y="250" font-size="18.5" fill="{MUTED}">Web, mobile and SaaS products,</text>'
        f'<text class="m" x="{x}" y="276" font-size="18.5" fill="{MUTED}">from requirements to release.</text></g>'
        f'<g{anim("rise", 0.8, T_HERO + 0.75)}>'
        f'<circle cx="{x + 6}" cy="319" r="5" fill="{MINT}"'
        + ("" if STATIC else f' style="animation:pulse 2.2s ease-in-out {T_HERO + 1.5}s infinite"')
        + f'/><text class="m" x="{x + 20}" y="324" font-size="16" fill="{WHITE}">Senior Project Manager at The Business Wings</text>'
        f'<text class="m" x="{x + 20}" y="350" font-size="15" fill="{MUTED}">Freelance since 2021 · Visakhapatnam, India</text></g>'
    )
    defs = (
        f'<defs><linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="140" y2="0">'
        f'<stop offset="0" stop-color="{MINT}" stop-opacity="0"/><stop offset=".5" stop-color="#C9F7E3" stop-opacity=".95"/>'
        f'<stop offset="1" stop-color="{MINT}" stop-opacity="0"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" values="300 0;300 0;900 0" '
        f'keyTimes="0;.55;1" dur="5s" begin="{T_HERO + 1.8}s" repeatCount="indefinite"/>'
        f"</linearGradient></defs>"
        if not STATIC
        else ""
    )
    css = (
        f"@keyframes scan{{0%{{opacity:1;transform:translateY(0)}}92%{{opacity:1}}"
        f"100%{{opacity:0;transform:translateY({art_h:.0f}px)}}}}"
        f"@keyframes travel{{0%{{opacity:0;transform:translateX(0)}}10%,90%{{opacity:1}}"
        f"100%{{opacity:0;transform:translateX({nodes[-1][1] - nodes[0][1]}px)}}}}"
    )
    return svg(
        W, H,
        "Krishna Chaitanya Doppa, Technical Project Manager: web, mobile and SaaS products, from requirements to release",
        frame(W, H) + defs + window + text + rail,
        extra_css=css,
    )


def graph(s: dict) -> str:
    W, H = 1000, 262
    step, cell = 16, 13
    days = s["days"]
    first = days[0][0]
    offset = (first.weekday() + 1) % 7  # Sunday = row 0
    n_weeks = (offset + len(days) + 6) // 7
    x0 = W - 36 - n_weeks * step + (step - cell)
    y0 = 112
    t0 = T_GRAPH + 0.3

    cells, months_seen = [], set()
    labels = []
    for i, (d, c) in enumerate(days):
        wk, dow = divmod(offset + i, 7)
        x, y = x0 + wk * step, y0 + dow * step
        delay = t0 + wk * 0.02 + dow * 0.012
        cells.append(
            f'<rect class="fb" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{GRAPH_LEVELS[level(c, s["quartiles"])]}"{anim("pop", 0.35, delay)}/>'
        )
        if d.day <= 7 and dow == 0 and (d.year, d.month) not in months_seen and wk < n_weeks - 1:
            months_seen.add((d.year, d.month))
            labels.append(
                f'<text class="mono" x="{x}" y="{y0 - 10}" font-size="11" fill="{DIM}">{d.strftime("%b")}</text>'
            )
    weekdays = "".join(
        f'<text class="mono" x="{x0 - 10}" y="{y0 + r * step + 10}" font-size="10.5" fill="{DIM}" text-anchor="end">{n}</text>'
        for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend_x = W - 36 - 5 * 16 - 40
    legend = (
        f'<text class="mono" x="{legend_x - 8}" y="246" font-size="11" fill="{DIM}" text-anchor="end">Less</text>'
        + "".join(
            f'<rect x="{legend_x + k * 16}" y="236" width="{cell}" height="{cell}" rx="3" fill="{c}"/>'
            for k, c in enumerate(GRAPH_LEVELS)
        )
        + f'<text class="mono" x="{legend_x + 5 * 16 + 4}" y="246" font-size="11" fill="{DIM}">More</text>'
    )
    head = (
        f'<g{anim("rise", 0.7, T_GRAPH)}><text class="b" x="36" y="50" font-size="23" letter-spacing="-.4" fill="{WHITE}">'
        f'<tspan fill="{MINT}">{s["total"]:,}</tspan> contributions in the last year</text>'
        f'<text class="m" x="36" y="76" font-size="14.5" fill="{MUTED}">'
        f"Most of my work lives in private client repositories, so the squares are what I can show.</text></g>"
        f'<text class="mono" x="{W - 36}" y="50" font-size="11" fill="{DIM}" text-anchor="end"'
        f'{anim("fade", 0.6, T_GRAPH + 0.2)}>updated {fmt_date(s["fetched"])}</text>'
    )
    return svg(
        W, H, f'{s["total"]:,} contributions in the last year',
        frame(W, H) + head + "".join(labels) + weekdays + "".join(cells) + legend,
    )


def activity(s: dict) -> str:
    W, H = 1000, 300
    months = s["months"]
    best = max(c for _, c in months) or 1
    left, right, base, max_h = 40, 600, 246, 132
    slot = (right - left) / len(months)
    bw = 28
    bars, labels = [], []
    best_i = max(range(len(months)), key=lambda i: months[i][1])
    for i, ((y, m), c) in enumerate(months):
        h = max(3, c / best * max_h)
        bx = left + i * slot + (slot - bw) / 2
        fill = MINT if i == best_i else "#2B636A"
        bars.append(
            f'<rect class="fbb" x="{bx:.1f}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" rx="4" fill="{fill}"'
            f'{anim("grow", 0.7, T_ACTIVITY + 0.3 + i * 0.06)}/>'
        )
        name = dt.date(y, m, 1).strftime("%b")
        labels.append(
            f'<text class="mono" x="{bx + bw / 2:.1f}" y="{base + 20}" font-size="11" fill="{DIM}" text-anchor="middle">{name}</text>'
        )
        if m == 1:
            labels.append(
                f'<text class="mono" x="{bx + bw / 2:.1f}" y="{base + 34}" font-size="10" fill="{DIM}" '
                f'fill-opacity=".7" text-anchor="middle">{y}</text>'
            )
    bh = max(3, months[best_i][1] / best * max_h)
    bx = left + best_i * slot + slot / 2
    peak = (
        f'<text class="b fb" x="{bx:.1f}" y="{base - bh - 9:.1f}" font-size="15" fill="{MINT}" text-anchor="middle"'
        f'{anim("pop", 0.45, T_ACTIVITY + 0.3 + len(months) * 0.06 + 0.3)}>{months[best_i][1]:,}</text>'
    )
    lr = s["longest_range"]
    stats = [
        # a 1- or 2-day streak undersells the year, so show the busiest week instead
        (f'{s["current"]}', "days", "Current streak", "as of " + fmt_date(s["fetched"], False))
        if s["current"] >= 3
        else (f'{s["best_week"]:,}', "", "Busiest week", "week of " + fmt_date(s["best_week_start"])),
        (f'{s["longest"]}', "days", "Longest streak",
         f"{fmt_date(lr[0], False)} – {fmt_date(lr[1], False)}" if lr[0] else ""),
        (f'{s["active"]}', "", "Active days", f"of the last {len(s['days'])}"),
        (f'{s["busiest"]:,}', "", "Busiest day", fmt_date(s["busiest_day"])),
    ]
    cells = []
    for k, (num, unit, label, sub) in enumerate(stats):
        cx = 664 + (k % 2) * 160
        cy = 112 + (k // 2) * 102
        u = f'<tspan class="m" font-size="15" fill="{MUTED}" dx="5">{unit}</tspan>' if unit else ""
        cells.append(
            f'<g{anim("rise", 0.7, T_ACTIVITY + 0.4 + k * 0.12)}>'
            f'<text class="b" x="{cx}" y="{cy}" font-size="34" letter-spacing="-1" fill="{WHITE}">{num}{u}</text>'
            f'<text class="m" x="{cx}" y="{cy + 24}" font-size="13.5" fill="{MUTED}">{label}</text>'
            f'<text class="mono" x="{cx}" y="{cy + 42}" font-size="11" fill="{DIM}">{esc(sub)}</text></g>'
        )
    head = (
        f'<g{anim("rise", 0.7, T_ACTIVITY)}><text class="b" x="36" y="50" font-size="20" fill="{WHITE}">Contributions per month</text>'
        f'<text class="m" x="36" y="74" font-size="14" fill="{MUTED}">Last 12 months. The best month is in mint.</text></g>'
        f'<path d="M632 36V264" stroke="{LINE}"/>'
        f'<path d="M{left} {base}H{right}" stroke="{LINE}"/>'
    )
    return svg(
        W, H,
        f'Contributions per month. Current streak {s["current"]} days, longest {s["longest"]} days, '
        f'{s["active"]} active days, busiest day {s["busiest"]} contributions',
        frame(W, H) + head + "".join(bars) + "".join(labels) + peak + "".join(cells),
    )


def tile(idx: int, label: str, number: int, unit: str, desc: str, cta: str) -> str:
    W, H = 330, 300
    t0 = T_TILES + idx * 0.18
    t_count = t0 + 0.55
    frames_n, frame_dt = 18, 0.05
    num_fmt = f"{number:,}"

    count = ""
    final_style = ""
    if not STATIC:
        for i in range(1, frames_n):
            v = round(number * (1 - (1 - i / frames_n) ** 3))
            count += (
                f'<text class="b cf" x="24" y="146" font-size="74" letter-spacing="-2.5" fill="{WHITE}" visibility="hidden">'
                f'{v:,}<set attributeName="visibility" to="visible" begin="{t_count + i * frame_dt:.3f}s" '
                f'dur="{frame_dt}s"/></text>'
            )
        final_style = f' style="animation:appear .01s linear {t_count + frames_n * frame_dt:.3f}s both"'
    number_el = (
        f'<text class="b" x="24" y="146" font-size="74" letter-spacing="-2.5" fill="{WHITE}"{final_style}>{num_fmt}</text>'
    )

    lines = wrap(desc, 34)
    desc_el = "".join(
        f'<text class="m" x="26" y="{204 + k * 21}" font-size="14.5" fill="{MUTED}">{esc(t)}</text>'
        for k, t in enumerate(lines)
    )
    fx = ""
    if not STATIC:
        fx = (
            f'<circle class="fx fb" cx="{W}" cy="0" r="110" fill="none" stroke="{MINT}" stroke-width="2" '
            f'style="animation:ring 3.2s ease-out {t0 + 1.4:.2f}s infinite"/>'
            f'<rect class="fx" x="-140" y="-40" width="70" height="{H + 80}" fill="url(#sweep)" transform="skewX(-16)" '
            f'style="animation:sweep 6s ease-in-out {t0 + 2.2:.2f}s infinite"/>'
        )
    defs = (
        f'<defs><linearGradient id="sweep" x1="0" x2="1"><stop offset="0" stop-color="{WHITE}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{WHITE}" stop-opacity=".09"/><stop offset="1" stop-color="{WHITE}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
    )
    arrow_style = "" if STATIC else f' style="animation:nudge 1.6s ease-in-out {t0 + 1.2:.2f}s infinite"'
    body = (
        f'<g class="fbb"{anim("swing", 1.0, t0)}>'
        + frame(W, H, accent_top=True)
        + defs
        + f'<g clip-path="url(#card)">{fx}</g>'
        + f'<text class="mono" x="26" y="44" font-size="12" letter-spacing="1.2" fill="{MINT}">{esc(label)}</text>'
        + count
        + number_el
        + f'<text class="b" x="26" y="176" font-size="17" fill="{WHITE}">{esc(unit)}</text>'
        + desc_el
        + f'<text class="m" x="26" y="274" font-size="14.5" fill="{MINT}">{esc(cta)}</text>'
        + f'<text class="m fb" x="{26 + len(cta) * 7.6 + 6:.0f}" y="274" font-size="14.5" fill="{MINT}"{arrow_style}>→</text>'
        + "</g>"
    )
    css = "@keyframes sweep{0%{transform:skewX(-16deg) translateX(0)}60%,100%{transform:skewX(-16deg) translateX(620px)}}"
    return svg(W, H, f"{num_fmt} {unit}. {desc}", body, extra_css=css)


WORK = [
    ("The Business Wings", "Senior Project Manager", "Mar 2025 – now", True,
     "Shipped the Advance Washing apps and WhatsApp ordering, from the CEO's brief to Google Play and the App Store."),
    ("Freelance, for EnValues and direct clients", "Technical project manager and developer", "Nov 2021 – now", True,
     "Built and run the platform behind EnOrbit, a WhatsApp automation SaaS. Built a live 3,104-product price "
     "catalogue for an electronics retailer."),
    ("AISMARTLIVE Solutions", "Technical Project Lead", "Mar 2022 – Jan 2025", False,
     "Led a team of 4–5 building Alankara AI, a MediaPipe virtual try-on."),
]
STACK = "React Native · Firebase · Supabase · PostgreSQL · REST APIs · Razorpay · Shopify · MediaPipe"


def work() -> str:
    W = 1000
    y = 104
    rows, dots, dot_ys = [], [], []
    for k, (org, role, when, current, desc) in enumerate(WORK):
        d = T_WORK + 0.25 + k * 0.22
        lines = wrap(desc, 116)
        dot = (
            f'<circle cx="48" cy="{y - 6}" r="6" fill="{MINT if current else TEAL}" stroke="{MINT}" stroke-width="2"'
            + ("" if STATIC or not current else f' style="animation:pulse 2.4s ease-in-out {d + 1:.2f}s infinite"')
            + "/>"
        )
        dots.append(f"<g{anim('fade', 0.4, d)}>{dot}</g>")
        dot_ys.append(y - 6)
        rows.append(
            f'<g{anim("slidein", 0.7, d)}>'
            f'<text class="b" x="72" y="{y}" font-size="18" fill="{WHITE}">{esc(org)}</text>'
            f'<text class="mono" x="{W - 36}" y="{y}" font-size="12" fill="{DIM}" text-anchor="end">{esc(when)}</text>'
            f'<text class="m" x="72" y="{y + 23}" font-size="14.5" fill="{MINT}">{esc(role)}</text>'
            + "".join(
                f'<text class="m" x="72" y="{y + 47 + j * 21}" font-size="14.5" fill="{MUTED}">{esc(t)}</text>'
                for j, t in enumerate(lines)
            )
            + "</g>"
        )
        y += 47 + len(lines) * 21 + 30
    H = y + 30
    line = (
        f'<path d="M48 {dot_ys[0]}V{dot_ys[-1]}" stroke="{LINE}" stroke-width="2" pathLength="1" '
        f'stroke-dasharray="1"{anim("draw", 1.0, T_WORK + 0.2, "ease-in-out")}/>'
    )
    head = (
        f'<g{anim("rise", 0.7, T_WORK)}><text class="b" x="36" y="56" font-size="20" fill="{WHITE}">Where I work</text></g>'
    )
    stack = (
        f'<path d="M36 {y - 24}H{W - 36}" stroke="{LINE}"/>'
        f'<text class="mono" x="36" y="{y + 2}" font-size="12" fill="{MUTED}"'
        f'{anim("fade", 0.6, T_WORK + 1.1)}>{esc(STACK)}</text>'
    )
    return svg(W, H, "Where I work: The Business Wings, freelance for EnValues and direct clients, AISMARTLIVE Solutions",
               frame(W, H) + head + line + "".join(dots) + "".join(rows) + stack)


TILES = [
    ("tile-requirements", "01 · REQUIREMENTS", 15, "client requirements",
     "traced to evidence in one audit for a retail pricing system", "Read the case study"),
    ("tile-testing", "02 · TESTING", 237, "automated tests",
     "plus 22 live acceptance checks on a 3,104-product catalogue", "Read the case study"),
    ("tile-delivery", "03 · DELIVERY", 5, "years shipping client software",
     "web, mobile and SaaS, from the first call to release", "See my LinkedIn"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = load_stats()
    cards = {"hero": hero(), "graph": graph(s), "activity": activity(s), "work": work()}
    for i, (name, *args) in enumerate(TILES):
        cards[name] = tile(i, *args)
    for name, content in cards.items():
        (OUT / f"{name}.svg").write_text(content)
        print(f"{name}.svg {len(content) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
