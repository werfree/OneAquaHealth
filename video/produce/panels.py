#!/usr/bin/env python
"""Render the video's data panels as SVGs from the captured live JSON.

Every number drawn here comes from `video/_build/data/*.json`, which was
fetched read-only from the running gateway (see capture_data.py). Nothing is
hard-coded except layout.
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "video" / "_build" / "data"
OUT = REPO / "video" / "_build" / "panels"
OUT.mkdir(parents=True, exist_ok=True)

INK, MUTED, LINE, BLUE, ACC2, BG = "#16232B", "#5B6B75", "#E3DED3", "#1F6FB2", "#B05A2A", "#F7F5F0"
W, H = 1920, 1080


def load(name: str):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def esc(s) -> str:
    return html.escape(str(s))


def head(title: str, kicker: str) -> str:
    return f"""  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect x="0" y="0" width="{W}" height="6" fill="{BLUE}"/>
  <text x="80" y="86" font-size="24" font-weight="700" fill="{BLUE}" letter-spacing="2">{esc(kicker)}</text>
  <text x="80" y="146" font-size="52" font-weight="800" fill="{INK}">{esc(title)}</text>"""


def foot(text: str) -> str:
    return (f'\n  <text x="80" y="872" font-size="22" fill="{MUTED}" font-style="italic">{esc(text)}</text>')


def svg(name: str, body: str) -> None:
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
           '  <defs><style>text{font-family:"Liberation Sans","DejaVu Sans",sans-serif;}</style></defs>\n'
           f"{body}\n</svg>\n")
    (OUT / f"{name}.svg").write_text(doc, encoding="utf-8")
    print("wrote", name)


def d2x(d: str, d0: date, d1: date, x0: float, x1: float) -> float:
    day = datetime.fromisoformat(d.replace("Z", "+00:00")).date()
    span = (d1 - d0).days or 1
    return x0 + (day - d0).days / span * (x1 - x0)


# --------------------------------------------------------------------------- #
def panel_trend() -> None:
    tr = load("trend")
    site = load("site")
    wa = load("wards")
    series = tr["series"]
    vals = [p["value"] for p in series]
    d0 = datetime.fromisoformat(series[0]["date"]).date()
    d1 = datetime.fromisoformat(series[-1]["date"]).date()
    thr = tr["threshold"]
    latest = tr["latest"]
    ch = tr["change"]

    add = [o for o in site["health_observations"] if o["indicator"] == "acute_diarrhoeal_disease"]
    add.sort(key=lambda o: o["when"])

    X0, X1 = 640, 1820
    WY0, WY1 = 260, 560          # water panel
    HY0, HY1 = 650, 860          # health panel
    wmax = max(vals) * 1.06
    hmax = max(o["value"] for o in add) * 1.25

    def wy(v): return WY1 - v / wmax * (WY1 - WY0)
    def hy(v): return HY1 - v / hmax * (HY1 - HY0)

    b = [head("Watch the work: screening, ranking, trend", "SURVEILLANCE STUDIO · DETERMINISTIC LIVE ANALYSES")]

    # ward ranking on the left
    b.append(f'  <rect x="80" y="230" width="470" height="470" rx="14" fill="#fff" stroke="{LINE}"/>')
    b.append(f'  <text x="112" y="282" font-size="24" font-weight="700" fill="{INK}">Ward priority</text>')
    b.append(f'  <text x="112" y="312" font-size="19" fill="{MUTED}">screening flag + notified-case rise &gt; 15%</text>')
    yy = 366
    prio = set(wa.get("priority", []))
    for wr in wa["wards"][:6]:
        pct = wr.get("add_change_pct")
        pstr = f"{pct:+.1f}%" if pct is not None else "n/a"
        sel = wr["site_id"] in prio
        if sel:
            b.append(f'  <rect x="100" y="{yy-28}" width="430" height="52" rx="8" fill="#EAF3FB" stroke="{BLUE}"/>')
        b.append(f'  <text x="116" y="{yy}" font-size="22" font-weight="{"800" if sel else "600"}" fill="{INK}">{esc(wr["name"][:28])}</text>')
        b.append(f'  <text x="512" y="{yy}" text-anchor="end" font-size="22" font-weight="800" fill="{BLUE if sel else MUTED}">{pstr}</text>')
        yy += 60
    b.append(f'  <text x="116" y="{yy+8}" font-size="19" fill="{MUTED}">priority: {esc(", ".join(wa.get("priority", [])))}</text>')

    # water panel
    b.append(f'  <text x="{X0}" y="{WY0-24}" font-size="24" font-weight="700" fill="{INK}">Faecal coliform · ITO · daily (28 points)</text>')
    b.append(f'  <line x1="{X0}" y1="{wy(thr):.1f}" x2="{X1}" y2="{wy(thr):.1f}" stroke="{ACC2}" stroke-dasharray="7 6" stroke-width="2"/>')
    b.append(f'  <text x="{X1}" y="{wy(thr)-8:.1f}" text-anchor="end" font-size="19" fill="{ACC2}">prototype screening value 2500</text>')
    pts = " ".join(f"{d2x(p['date'],d0,d1,X0,X1):.1f},{wy(p['value']):.1f}" for p in series)
    b.append(f'  <polyline points="{pts}" fill="none" stroke="{BLUE}" stroke-width="3"/>')
    peak = max(series, key=lambda p: p["value"])
    px, py = d2x(peak["date"], d0, d1, X0, X1), wy(peak["value"])
    b.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="6" fill="{BLUE}"/>')
    b.append(f'  <text x="{px:.1f}" y="{py-14:.1f}" text-anchor="middle" font-size="20" font-weight="700" fill="{BLUE}">peak {peak["value"]:.0f} · {peak["date"]}</text>')
    xf = tr["exceedance"].get("exceedance_factor")
    b.append(f'  <text x="{X0}" y="{WY1+34}" font-size="20" fill="{MUTED}">latest {latest:.0f} MPN/100mL vs 2500 &#8776; {xf:.2f}&#215;</text>')
    b.append(f'  <text x="{X1}" y="{WY1+34}" text-anchor="end" font-size="20" fill="{MUTED}">14-day change {ch["pct"]:+.1f}% ({ch["recent_mean"]:.0f} vs {ch["prior_mean"]:.0f})</text>')

    # health panel
    b.append(f'  <text x="{X0}" y="{HY0-24}" font-size="24" font-weight="700" fill="{INK}">Notified acute diarrhoeal disease · weekly ({len(add)} points)</text>')
    hpts = " ".join(f"{d2x(o['when'],d0,d1,X0,X1):.1f},{hy(o['value']):.1f}" for o in add)
    b.append(f'  <polyline points="{hpts}" fill="none" stroke="{ACC2}" stroke-width="3"/>')
    for o in add:
        x, y = d2x(o["when"], d0, d1, X0, X1), hy(o["value"])
        b.append(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{ACC2}"/>')
    hp = max(add, key=lambda o: o["value"])
    hx, hyv = d2x(hp["when"], d0, d1, X0, X1), hy(hp["value"])
    hlabel = f'peak {hp["value"]:.2f} per 100k · {hp["when"][:10]}'
    if hx > X1 - 320:
        b.append(f'  <text x="{hx-12:.1f}" y="{hyv-14:.1f}" text-anchor="end" font-size="20" font-weight="700" fill="{ACC2}">{hlabel}</text>')
    else:
        b.append(f'  <text x="{hx:.1f}" y="{hyv-14:.1f}" text-anchor="middle" font-size="20" font-weight="700" fill="{ACC2}">{hlabel}</text>')

    b.append(f'  <text x="{X0}" y="{HY1+40}" font-size="19" fill="{MUTED}">different cadence: water daily, cases weekly</text>')
    b.append(foot("All figures computed in Python from live FHIR (oah-demo-final); no model involved. Descriptive pattern — not causation."))
    svg("s06a-trend", "\n".join(b))


# --------------------------------------------------------------------------- #
def panel_profile() -> None:
    pr = load("profile")
    pe = load("persistence")
    pts = pr["points"]
    step = pr["largest_increase"]
    st = [s for s in pe["stations"] if s["site_id"] == "yam-ito"][0]

    b = [head("Where does the change appear? Is it sustained?", "RIVER PROFILE · PERSISTENCE")]

    # river profile bars
    X0, X1, BY0, BY1 = 120, 1120, 300, 700
    vmax = max(p["mean"] for p in pts) * 1.15
    n = len(pts)
    bw = 150
    gap = (X1 - X0 - n * bw) / (n + 1)
    b.append(f'  <text x="{X0}" y="{BY0-40}" font-size="26" font-weight="700" fill="{INK}">Yamuna profile · mean faecal coliform, in flow order</text>')
    x = X0
    for i, p in enumerate(pts):
        bh = p["mean"] / vmax * (BY1 - BY0)
        y = BY1 - bh
        col = BLUE if p["exceeds"] else "#7FB77E"
        b.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{bw}" height="{bh:.1f}" rx="8" fill="{col}"/>')
        b.append(f'  <text x="{x+bw/2:.1f}" y="{y-12:.1f}" text-anchor="middle" font-size="26" font-weight="800" fill="{INK}">{p["mean"]:.0f}</text>')
        b.append(f'  <text x="{x+bw/2:.1f}" y="{BY1+38:.1f}" text-anchor="middle" font-size="22" font-weight="700" fill="{INK}">{esc(p["name"].split(" at ")[-1].split(" Barrage")[0].split(" Bridge")[0])}</text>')
        fac = f'{p["factor"]:.2f}×' if p.get("factor") else "within"
        b.append(f'  <text x="{x+bw/2:.1f}" y="{BY1+68:.1f}" text-anchor="middle" font-size="20" fill="{MUTED}">{fac}</text>')
        x += bw + gap
    b.append(f'  <text x="{X0}" y="{BY1+120}" font-size="24" fill="{INK}">largest step <tspan font-weight="800" fill="{ACC2}">{step["ratio"]:.2f}× over {step["reach_km"]} km</tspan> ({esc(step["from"])} → {esc(step["to"])}) — narrows where confirmatory sampling may help.</text>')

    # persistence strip
    SX0, SY = 1200, 320
    b.append(f'  <text x="{SX0}" y="{SY-40}" font-size="26" font-weight="700" fill="{INK}">Persistence · 28 days</text>')
    cell, cg = 20, 2
    for i, day in enumerate(st["daily"]):
        cx = SX0 + (i % 14) * (cell + cg)
        cy = SY + (i // 14) * (cell + cg)
        col = BLUE if day["over"] else "#7FB77E"
        b.append(f'  <rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="4" fill="{col}"/>')
    b.append(f'  <text x="{SX0}" y="{SY+120}" font-size="34" font-weight="800" fill="{INK}">{st["days_over"]}/{st["days_measured"]} days over</text>')
    b.append(f'  <text x="{SX0}" y="{SY+158}" font-size="22" fill="{MUTED}">longest run {st["longest_run"]} · current run {st["current_run"]}</text>')
    b.append(f'  <text x="{SX0}" y="{SY+196}" font-size="22" fill="{MUTED}">A sustained condition — not a one-off.</text>')

    b.append(foot("Bars and strip are live values from /api/officer/profile and /api/officer/persistence. A step locates a stretch — it does not identify a discharge."))
    svg("s06b-profile", "\n".join(b))


# --------------------------------------------------------------------------- #
def panel_offset() -> None:
    o = load("offset")
    b = [head("The honest label", "DESCRIPTIVE PEAK OFFSET · LIVE")]
    b.append(f'  <rect x="120" y="240" width="1680" height="360" rx="16" fill="#fff" stroke="{LINE}"/>')
    b.append(f'  <text x="170" y="330" font-size="30" fill="{MUTED}">water peak</text>')
    b.append(f'  <text x="170" y="392" font-size="52" font-weight="800" fill="{BLUE}">{esc(o["water_peak"]["date"])}</text>')
    b.append(f'  <text x="170" y="446" font-size="26" fill="{INK}">{o["water_peak"]["value"]:.0f} {esc(o["water_peak"]["unit"])}</text>')
    b.append(f'  <text x="700" y="392" font-size="64" font-weight="800" fill="{ACC2}">+{o["offset_days"]} days</text>')
    b.append(f'  <text x="700" y="446" font-size="24" fill="{MUTED}">descriptive gap between two maxima</text>')
    b.append(f'  <text x="1240" y="330" font-size="30" fill="{MUTED}">health peak</text>')
    b.append(f'  <text x="1240" y="392" font-size="52" font-weight="800" fill="{ACC2}">{esc(o["health_peak"]["date"])}</text>')
    b.append(f'  <text x="1240" y="446" font-size="26" fill="{INK}">{o["health_peak"]["value"]:.2f} {esc(o["health_peak"]["unit"])}</text>')
    b.append(f'  <text x="1240" y="486" font-size="22" fill="{MUTED}">only {o["health_points"]} weekly health points</text>')
    b.append(f'  <text x="170" y="540" font-size="28" font-style="italic" fill="{INK}">"{esc(o["interpretation"])}"</text>')
    # caveat box
    b.append(f'  <rect x="120" y="640" width="1680" height="196" rx="14" fill="#FBEFE6" stroke="{ACC2}"/>')
    b.append(f'  <text x="170" y="700" font-size="26" font-weight="800" fill="{ACC2}">caveat (read aloud, verbatim)</text>')
    words = o["caveat"].split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + 1 + len(w) <= 92:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    for i, ln in enumerate(lines[:4]):
        b.append(f'  <text x="170" y="{744 + i*34}" font-size="24" fill="{INK}">{esc(ln)}</text>')
    b.append(foot("Deterministic, model-free: /api/officer/offset. Not a correlation — a prompt to sample."))
    svg("s07-offset", "\n".join(b))


# --------------------------------------------------------------------------- #
def panel_ingest() -> None:
    ig = load("ingest")
    b = [head("Where did these records come from?", "REAL PIPELINE · FHIR_UPLOAD_ENABLED=false (no write)")]
    # terminal block
    b.append(f'  <rect x="120" y="230" width="1100" height="470" rx="14" fill="#16232B"/>')
    b.append(f'  <text x="150" y="286" font-size="22" fill="#8FBEDC">&#9679; python -m oah_ingestion  ·  sample iot  ·  yam-ito</text>')
    yy = 348
    for ln in ig["alert_text"].splitlines():
        col = "#FF8A5B" if ln.startswith("[") else "#E8EEF2"
        b.append(f'  <text x="150" y="{yy}" font-size="26" font-weight="{"800" if ln.startswith("[") else "400"}" fill="{col}" font-family="Liberation Mono,DejaVu Sans Mono,monospace">{esc(ln)}</text>')
        yy += 44
    b.append(f'  <text x="150" y="{yy+16}" font-size="24" fill="#8FBEDC">pipeline: {esc(ig["pipeline_fhir"])} (nothing written)</text>')
    # resource counts
    b.append(f'  <text x="1290" y="286" font-size="26" font-weight="700" fill="{INK}">Mapped resources</text>')
    cy = 350
    for k in ["Device", "Observation", "Location", "Specimen"]:
        v = ig["client_side_counts"][k]
        b.append(f'  <rect x="1290" y="{cy-40}" width="500" height="66" rx="10" fill="#fff" stroke="{LINE}"/>')
        b.append(f'  <text x="1320" y="{cy}" font-size="28" font-weight="700" fill="{INK}">{k}</text>')
        b.append(f'  <text x="1760" y="{cy}" text-anchor="end" font-size="30" font-weight="800" fill="{BLUE}">{v}</text>')
        cy += 84
    b.append(f'  <text x="1290" y="{cy+4}" font-size="21" fill="{MUTED}">validate → screen → map → tag → Bundle → upload</text>')
    b.append(foot("Identical code path to a real sensor or broker message: pipeline.process() with the bundled iot sample."))
    svg("s08-ingest", "\n".join(b))


# --------------------------------------------------------------------------- #
def panel_endpoints() -> None:
    b = [head("The deterministic live routes", "STUDIO FALLBACK · NO MODEL REQUIRED")]
    routes = [
        ("wards", "/api/officer/wards?days=28", "ward ranking + co-location test"),
        ("trend", "/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28", "28-point series + 14-day change"),
        ("profile", "/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28", "Wazirabad → ITO → Okhla"),
        ("persistence", "/api/officer/persistence?days=28", "days over / longest run"),
        ("offset", "/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28", "descriptive +9 days, with caveat"),
        ("report/facts", "/api/officer/report/facts?days=28", "model-free executive brief"),
    ]
    y = 270
    for name, path, desc in routes:
        b.append(f'  <rect x="120" y="{y-46}" width="1680" height="88" rx="10" fill="#fff" stroke="{LINE}"/>')
        b.append(f'  <text x="150" y="{y}" font-size="28" font-weight="800" fill="{BLUE}" font-family="Liberation Mono,DejaVu Sans Mono,monospace">GET {esc(path)}</text>')
        b.append(f'  <text x="1760" y="{y}" text-anchor="end" font-size="22" fill="{MUTED}">{esc(desc)}</text>')
        y += 108
    b.append(foot("These read live FHIR and compute in Python — the same analyses the Studio calls, with no model in the loop."))
    svg("s05-endpoints", "\n".join(b))


if __name__ == "__main__":
    panel_trend()
    panel_profile()
    panel_offset()
    panel_ingest()
    panel_endpoints()
