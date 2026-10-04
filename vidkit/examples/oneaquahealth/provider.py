"""OneAquaHealth provider for vidkit.

Bridges vidkit to the running OneAquaHealth services:

* ``datasets(ctx)`` fetches the live evidence **read-only** from the gateway and
  also runs the bundled ``iot`` sample through the real pipeline with
  ``FHIR_UPLOAD_ENABLED=false`` (so nothing is written to the shared server).
* ``register()`` adds four project-specific panel renderers.
* ``panels()`` maps each panel name to a renderer + dataset.

Nothing here writes to the FHIR server; every value on screen is either read from
the gateway or computed by the repo's own code.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from vidkit import panels as panel_lib
from vidkit.svg import PanelDoc, circle, esc, line, polyline, rect, text, text_block, THEME

# The OneAquaHealth repo root (vidkit/examples/oneaquahealth -> repo).
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GATEWAY = os.getenv("OAH_GATEWAY", "http://127.0.0.1:8000")


# --------------------------------------------------------------------------- #
def _get(path: str) -> Any:
    with urllib.request.urlopen(GATEWAY + path, timeout=120) as r:
        return json.load(r)


# --------------------------------------------------------------------------- #
# Custom panel renderers (the extension point)
# --------------------------------------------------------------------------- #
def _oah_trend(data: dict, opt: dict, doc: PanelDoc) -> None:
    t = THEME
    wards = data.get("wards", [])

    def norm_series(raw: list) -> list[tuple[str, float]]:
        out = []
        for p in raw:
            if isinstance(p, dict):
                out.append((str(p.get("x", "")), float(p.get("y", 0))))
            else:
                out.append((str(p[0]), float(p[1])))
        return out

    series = [{"label": s["label"], "color": s["color"],
               "peak_prefix": s.get("peak_prefix", "peak"),
               "points": norm_series(s["points"])} for s in data.get("series", [])]
    thresholds = data.get("thresholds", [])
    summary = data.get("summary", {})

    # ward ranking sidebar
    doc.add(rect(80, 230, 470, 560, rx=14, fill=t.panel, stroke=t.line),
            text(112, 282, "Ward priority", size=24, weight=700),
            text(112, 312, "screening flag + notified-case rise > 15%", size=19, fill=t.muted))
    y = 372
    for w in wards[:6]:
        sel = bool(w.get("priority"))
        if sel:
            doc.add(rect(100, y - 28, 430, 52, rx=8, fill="#EAF3FB", stroke=t.accent))
        doc.add(text(116, y, w["name"][:28], size=22, weight=800 if sel else 600),
                text(512, y, w.get("change", "n/a"), size=22, weight=800,
                     fill=t.accent if sel else t.muted, anchor="end"))
        y += 60

    # two stacked panels, each with its own y-axis
    x0, x1 = 640, 1820
    panels = series[:2]
    panels_def = [(250, 500, "water"), (600, 850, "health")]
    for (y0, y1, _tag), s in zip(panels_def, panels):
        pts_raw = s["points"]
        ymax = max((v for _, v in pts_raw), default=1) * 1.15
        n = max(len(pts_raw) - 1, 1)
        pts = [(x0 + i / n * (x1 - x0), y1 - v / ymax * (y1 - y0))
               for i, (_, v) in enumerate(pts_raw)]
        if _tag == "water":
            for th in thresholds:
                yy = y1 - th["value"] / ymax * (y1 - y0)
                doc.add(line(x0, yy, x1, yy, stroke=t.accent2, dash="7 6", sw=2),
                        text(x1, yy - 8, th["label"], size=19, fill=t.accent2, anchor="end"))
        doc.add(polyline(pts, stroke=s["color"]),
                text(x0, y0 - 24, s["label"], size=22, weight=700))
        if pts_raw:
            pi = max(range(len(pts_raw)), key=lambda k: pts_raw[k][1])
            px, py = pts[pi]
            anchor = "end" if px > x1 - 340 else "middle"
            doc.add(circle(px, py, 6, fill=s["color"]),
                    text(px - (12 if anchor == "end" else 0), py - 14,
                         s.get("peak_prefix", "peak") + f" {pts_raw[pi][1]:,.0f}",
                         size=20, weight=700, fill=s["color"], anchor=anchor))

    if summary:
        doc.add(text(x0, 900, summary.get("left", ""), size=20, fill=t.muted),
                text(x1, 900, summary.get("right", ""), size=20, fill=t.muted,
                     anchor="end"))


def _oah_profile(data: dict, opt: dict, doc: PanelDoc) -> None:
    t = THEME
    bars = data.get("bars", [])
    strip = data.get("strip", {})
    x0, x1, y0, y1 = 120, 1120, 340, 700
    vmax = max((b["value"] for b in bars), default=1) * 1.15
    n = max(len(bars), 1)
    bw = 150
    gap = (x1 - x0 - n * bw) / (n + 1)
    x = x0
    for b in bars:
        bh = b["value"] / vmax * (y1 - y0)
        yy = y1 - bh
        col = t.accent if b.get("highlight") else t.good
        doc.add(rect(x, yy, bw, bh, rx=8, fill=col),
                text(x + bw / 2, yy - 12, f"{b['value']:,.0f}", size=26, weight=800,
                     anchor="middle"),
                text(x + bw / 2, y1 + 38, b["label"], size=22, weight=700, anchor="middle"),
                text(x + bw / 2, y1 + 68, b.get("note", ""), size=20, fill=t.muted,
                     anchor="middle"))
        x += bw + gap
    doc.add(text(x0, y0 - 40, opt.get("title", "River profile"), size=26, weight=700))
    if data.get("caption"):
        doc.add(text(x0, y1 + 120, data["caption"], size=24))

    sx, sy = 1200, 320
    doc.add(text(sx, sy - 40, "Persistence · 28 days", size=26, weight=700))
    cell, cg, per_row = 20, 2, 14
    for i, on in enumerate(strip.get("cells", [])):
        doc.add(rect(sx + (i % per_row) * (cell + cg), sy + (i // per_row) * (cell + cg),
                     cell, cell, rx=4, fill=t.accent if on else t.good))
    doc.add(text(sx, sy + 120, strip.get("headline", ""), size=34, weight=800))
    for i, s in enumerate(strip.get("sub", [])[:2]):
        doc.add(text(sx, sy + 158 + i * 38, s, size=22, fill=t.muted))


def _oah_offset(data: dict, opt: dict, doc: PanelDoc) -> None:
    t = THEME
    doc.add(rect(120, 240, 1680, 360, rx=16, fill=t.panel, stroke=t.line),
            text(170, 330, "water peak", size=30, fill=t.muted),
            text(170, 392, data["water_peak"]["date"], size=52, weight=800, fill=t.accent),
            text(170, 446, f"{data['water_peak']['value']:,.0f} {data['water_peak']['unit']}",
                 size=26),
            text(700, 392, f"+{data['offset_days']} days", size=64, weight=800, fill=t.accent2),
            text(700, 446, "descriptive gap between two maxima", size=24, fill=t.muted),
            text(1240, 330, "health peak", size=30, fill=t.muted),
            text(1240, 392, data["health_peak"]["date"], size=52, weight=800, fill=t.accent2),
            text(1240, 446, f"{data['health_peak']['value']:.2f} {data['health_peak']['unit']}",
                 size=26),
            text(1240, 486, f"only {data['health_points']} weekly health points", size=22,
                 fill=t.muted),
            text(170, 540, f'"{data["interpretation"]}"', size=28, italic=True))
    doc.add(rect(120, 640, 1680, 196, rx=14, fill="#FBEFE6", stroke=t.accent2),
            text(170, 700, "caveat (read aloud, verbatim)", size=26, weight=800,
                 fill=t.accent2))
    doc.add(text_block(170, 744, data["caveat"], size=24, width=92, line_height=34,
                       max_lines=4))


def _oah_ingest(data: dict, opt: dict, doc: PanelDoc) -> None:
    t = THEME
    doc.add(rect(120, 230, 1100, 470, rx=14, fill=t.dark),
            text(150, 286, data.get("header", ""), size=22, fill=t.darkaccent))
    y = 348
    for ln in data["lines"]:
        colour = "#FF8A5B" if ln.startswith("[") else t.darktext
        doc.add(text(150, y, ln, size=26, fill=colour,
                     weight=800 if ln.startswith("[") else 400, mono=True))
        y += 44
    doc.add(text(150, y + 16, data.get("pipeline", ""), size=24, fill=t.darkaccent))
    doc.add(text(1290, 286, "Mapped resources", size=26, weight=700))
    cy = 350
    for k, v in data["counts"].items():
        doc.add(rect(1290, cy - 40, 500, 66, rx=10, fill=t.panel, stroke=t.line),
                text(1320, cy, k, size=28, weight=700),
                text(1760, cy, str(v), size=30, weight=800, fill=t.accent, anchor="end"))
        cy += 84


def register() -> None:
    panel_lib.register("oah_trend", _oah_trend)
    panel_lib.register("oah_profile", _oah_profile)
    panel_lib.register("oah_offset", _oah_offset)
    panel_lib.register("oah_ingest", _oah_ingest)


# --------------------------------------------------------------------------- #
# Datasets
# --------------------------------------------------------------------------- #
def _ingest_sample() -> dict:
    """Run the bundled `iot` sample through the real pipeline, upload disabled."""
    os.environ["FHIR_UPLOAD_ENABLED"] = "false"
    for src in ("oah-ingestion/src", "oah-pydantic-models/src", "oah-agent/src"):
        p = str(REPO / src)
        if p not in sys.path:
            sys.path.insert(0, p)
    from pydantic import TypeAdapter  # noqa: PLC0415

    from oah_ingestion.alerts import assess, format_alert  # noqa: PLC0415
    from oah_ingestion.envelope import IngestionEnvelope, envelope_as_message  # noqa: PLC0415
    from oah_ingestion.fhir_adapter import envelope_to_fhir  # noqa: PLC0415
    from oah_ingestion.pipeline import process  # noqa: PLC0415

    raw = json.loads((REPO / "demo/sample_iot_telemetry.json").read_text(encoding="utf-8"))
    env = TypeAdapter(IngestionEnvelope).validate_python(raw)
    counts = Counter(r.resourceType for r in envelope_to_fhir(env))
    result = process(env, envelope_as_message(env))
    return {
        "lines": format_alert(assess(env)).splitlines(),
        "counts": {k: counts[k] for k in ("Device", "Observation", "Location", "Specimen")},
        "pipeline": f"pipeline: {result.get('fhir')} (nothing written)",
        "header": "python -m oah_ingestion  ·  sample iot  ·  yam-ito",
    }


def datasets(ctx) -> dict[str, Any]:
    trend = _get("/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28")
    site = _get("/api/sites/yam-ito")
    profile = _get("/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28")
    persistence = _get("/api/officer/persistence?days=28")
    offset = _get("/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28")
    wards = _get("/api/officer/wards?days=28")

    water = [{"x": p["date"], "y": p["value"]} for p in trend["series"]]
    add = sorted((o for o in site["health_observations"]
                  if o["indicator"] == "acute_diarrhoeal_disease"),
                 key=lambda o: o["when"])
    health = [{"x": o["when"][:10], "y": o["value"]} for o in add]

    st = next((s for s in persistence["stations"] if s["site_id"] == "yam-ito"), {})
    prio = set(wards.get("priority", []))
    ward_rows = [{"name": w["name"].split(" at ")[-1].split(" Bridge")[0],
                  "change": (f"{w['add_change_pct']:+.1f}%" if w.get("add_change_pct")
                             is not None else "n/a"),
                  "priority": w["site_id"] in prio}
                 for w in wards["wards"][:6]]
    step = profile["largest_increase"]

    return {
        "trend": {
            "series": [
                {"label": f"Faecal coliform · daily ({len(water)} points)",
                 "points": water, "color": THEME.accent, "peak_prefix": "water peak"},
                {"label": f"Notified ADD · weekly ({len(health)} points)",
                 "points": health, "color": THEME.accent2, "peak_prefix": "case peak"},
            ],
            "thresholds": [{"value": trend["threshold"], "label": "prototype screening value 2500"}],
            "wards": ward_rows,
            "summary": {
                "left": f"latest {trend['latest']:,.0f} vs 2500 ≈ "
                        f"{trend['exceedance']['exceedance_factor']:.2f}×",
                "right": f"14-day change {trend['change']['pct']:+.1f}% "
                         f"({trend['change']['recent_mean']:,.0f} vs {trend['change']['prior_mean']:,.0f})",
            },
        },
        "profile": {
            "bars": [
                {"label": p["name"].split(" at ")[-1].split(" Barrage")[0].split(" Bridge")[0],
                 "value": p["mean"], "highlight": bool(p["exceeds"]),
                 "note": f"{p['factor']:.2f}×" if p.get("factor") else "within"}
                for p in profile["points"]
            ],
            "caption": f"largest step {step['ratio']:.2f}× over {step['reach_km']} km "
                       f"({step['from']} → {step['to']}) — narrows where confirmatory sampling may help.",
            "strip": {"cells": [d["over"] for d in st.get("daily", [])],
                      "headline": f"{st.get('days_over')}/{st.get('days_measured')} days over",
                      "sub": [f"longest run {st.get('longest_run')} · current run {st.get('current_run')}",
                              "A sustained condition — not a one-off."]},
        },
        "offset": offset,
        "ingest": _ingest_sample(),
        "endpoints": [
            {"path": "/api/officer/wards?days=28", "note": "ward ranking + co-location test"},
            {"path": "/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28",
             "note": "28-point series + 14-day change"},
            {"path": "/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28",
             "note": "Wazirabad → ITO → Okhla"},
            {"path": "/api/officer/persistence?days=28", "note": "days over / longest run"},
            {"path": "/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28",
             "note": "descriptive +9 days, with caveat"},
            {"path": "/api/officer/report/facts?days=28", "note": "model-free executive brief"},
        ],
    }


def panels() -> dict[str, Any]:
    return {
        "endpoints": {"kind": "endpoints", "dataset": "endpoints",
                      "options": {"title": "The deterministic live routes",
                                  "kicker": "STUDIO FALLBACK · NO MODEL REQUIRED"}},
        "trend": {"kind": "oah_trend", "dataset": "trend",
                  "options": {"title": "Watch the work: screening, ranking, trend",
                              "kicker": "SURVEILLANCE STUDIO · DETERMINISTIC LIVE ANALYSES"}},
        "profile": {"kind": "oah_profile", "dataset": "profile",
                    "options": {"title": "Where does the change appear? Is it sustained?",
                                "kicker": "RIVER PROFILE · PERSISTENCE"}},
        "offset": {"kind": "oah_offset", "dataset": "offset",
                   "options": {"title": "The honest label",
                               "kicker": "DESCRIPTIVE PEAK OFFSET · LIVE"}},
        "ingest": {"kind": "oah_ingest", "dataset": "ingest",
                   "options": {"title": "Where did these records come from?",
                               "kicker": "REAL PIPELINE · FHIR_UPLOAD_ENABLED=false (no write)"}},
    }
