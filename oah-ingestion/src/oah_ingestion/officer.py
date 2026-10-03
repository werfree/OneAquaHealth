"""API for the District Surveillance Officer panel.

The audience is a DSO in an IDSP/IHIP district surveillance unit, whose job is
to decide whether a change in syndromic notifications has an environmental
explanation worth escalating to the State Pollution Control Board.

That shapes every route here. The officer does not want a dashboard of current
values; they want to know what *moved*, in which ward, and whether it moved
before or after the cases did. So:

- `/api/officer/trend` returns a series, not a snapshot, with the change
  against the preceding window already computed.
- `/api/officer/wards` ranks wards by the combination of water exceedance and
  notification rise, which is the triage order the officer actually works in.
- `/api/officer/report` produces an executive brief whose numbers are derived
  in Python; the model writes prose over facts it cannot alter.
- `/api/officer/export/*` emits CSV and a FHIR Bundle, because the officer's
  next step is attaching evidence to an incident record, and that record is
  ABDM-aligned FHIR.

Nothing here is cached or pre-computed: every response is read from the FHIR
server at request time.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path

from .fhir_client import base_url, search, search_url
from .pipeline import dataset_tag
from .sites import registry
from .thresholds import THRESHOLDS, evaluate, severity_of

logger = logging.getLogger("OAH_Officer")
router = APIRouter(prefix="/api/officer", tags=["officer"])

STATIC = Path(__file__).resolve().parent / "static"

WATER_PROFILE = "observation-indicators-oah"
COMPONENT_PROFILE = "observation-with-component-oah"
HEALTH_PROFILE = "observation-health-measure-oah"
BASE = "http://hl7.eu/fhir/ig/oah/StructureDefinition/"
TAG_SYSTEM = "http://hl7.eu/fhir/ig/oah/CodeSystem/dataset-tag"

WATERBORNE = ["acute_diarrhoeal_disease", "cholera", "enteric_fever", "viral_hepatitis_a_e"]


def _tag() -> str:
    return f"{TAG_SYSTEM}|{dataset_tag()}"


def _value(obs: dict) -> Optional[float]:
    if "valueQuantity" in obs:
        return obs["valueQuantity"].get("value")
    for component in obs.get("component", []):
        code = (component.get("code", {}).get("coding") or [{}])[0].get("code")
        if code in {"value", "average"} and "valueQuantity" in component:
            return component["valueQuantity"].get("value")
    return None


def _component(obs: dict, code: str) -> Optional[float]:
    for component in obs.get("component", []):
        if (component.get("code", {}).get("coding") or [{}])[0].get("code") == code:
            return (component.get("valueQuantity") or {}).get("value")
    return None


def _flatten(obs: dict) -> dict:
    coding = (obs.get("code", {}).get("coding") or [{}])[0]
    when = obs.get("effectiveDateTime") or (obs.get("effectivePeriod") or {}).get("start")
    return {
        "id": obs.get("id"),
        "indicator": coding.get("code"),
        "site_id": (obs.get("subject", {}).get("reference") or "").replace("Location/", ""),
        "when": when,
        "date": (when or "")[:10],
        "value": _value(obs),
        "unit": (obs.get("valueQuantity") or {}).get("unit"),
        "cases": _component(obs, "cases"),
        "population": _component(obs, "populationAtRisk"),
        "baseline": _component(obs, "baseline"),
        "cohort": (obs.get("focus") or [{}])[0].get("reference", "").replace("Group/", "") or None,
    }


def _fetch(profile: str, *, site_id=None, indicator=None, since=None, until=None, limit=800) -> List[dict]:
    params: Dict[str, str] = {"_profile": BASE + profile, "_tag": _tag(), "_count": str(limit), "_sort": "date"}
    if site_id:
        params["subject"] = f"Location/{site_id}"
    if indicator:
        params["code"] = indicator
    bounds = []
    if since:
        bounds.append(f"ge{since}")
    if until:
        bounds.append(f"le{until}")
    if bounds:
        params["date"] = ",".join(bounds)
    return [_flatten(o) for o in search("Observation", params)]


def _water(**kw) -> List[dict]:
    """Water readings span two profiles depending on whether stats were sent."""

    rows = _fetch(WATER_PROFILE, **kw) + _fetch(COMPONENT_PROFILE, **kw)
    return sorted([r for r in rows if r["value"] is not None], key=lambda r: r["when"] or "")


@router.get("/stations")
def stations():
    """Every station, with its district, reach and current standing."""

    gazetteer = registry()
    out = []
    for site_id, site in gazetteer.items():
        out.append(
            {
                "site_id": site_id,
                "name": site.name,
                "city": site.city,
                "district": getattr(site, "district", None),
                "reach": getattr(site, "reach", None),
                "latitude": site.latitude,
                "longitude": site.longitude,
            }
        )
    return {"stations": out, "count": len(out)}


@router.get("/trend")
def trend(
    site_id: str = Query(..., description="Station id"),
    indicator: str = Query(..., description="Indicator code"),
    days: int = Query(28, ge=2, le=365),
):
    """A series for one indicator at one station, with the change already computed.

    The officer's question is comparative, so the comparison is done here rather
    than left to the reader: the most recent week against the week before it.
    """

    until = datetime.now(timezone.utc).date()
    since = until - timedelta(days=days)
    health = indicator in WATERBORNE
    rows = (
        _fetch(HEALTH_PROFILE, site_id=site_id, indicator=indicator, since=since.isoformat())
        if health
        else _water(site_id=site_id, indicator=indicator, since=since.isoformat())
    )
    series = [
        {"date": r["date"], "value": r["value"], "cases": r["cases"], "baseline": r["baseline"]}
        for r in rows
        if r["value"] is not None
    ]

    # Split on the midpoint of the window, not on a fixed index count. Water is
    # sampled daily and IDSP returns weekly, so `series[-7:]` means "the last
    # week" for one and "the whole window" for the other -- which silently
    # produced no comparison at all for the surveillance series.
    change = None
    if len(series) >= 2:
        midpoint = (datetime.now(timezone.utc).date() - timedelta(days=days // 2)).isoformat()
        recent = [p["value"] for p in series if p["date"] >= midpoint and p["value"] is not None]
        prior = [p["value"] for p in series if p["date"] < midpoint and p["value"] is not None]
        if not recent or not prior:          # too few points to split; use last vs previous
            recent, prior = [series[-1]["value"]], [series[-2]["value"]]
        a, b = sum(recent) / len(recent), sum(prior) / len(prior)
        change = {
            "recent_mean": round(a, 2),
            "prior_mean": round(b, 2),
            "pct": round((a - b) / b * 100, 1) if b else None,
            "direction": "up" if a > b else "down" if a < b else "flat",
            "basis": f"mean of the most recent {days // 2} days against the {days // 2} before",
        }

    rule = THRESHOLDS.get(indicator, {})
    latest = series[-1]["value"] if series else None
    return {
        "site_id": site_id,
        "indicator": indicator,
        "unit": rows[0]["unit"] if rows else rule.get("unit"),
        "series": series,
        "points": len(series),
        "latest": latest,
        "change": change,
        "threshold": rule.get("limit") or (f"{rule['range'][0]}-{rule['range'][1]}" if rule.get("range") else None),
        "threshold_basis": rule.get("basis"),
        "exceedance": evaluate(indicator, latest, rows[-1]["unit"] if rows else None) if latest is not None else None,
        "fhir_url": search_url("Observation", {"_profile": BASE + (HEALTH_PROFILE if health else WATER_PROFILE),
                                               "_tag": _tag(), "code": indicator,
                                               "subject": f"Location/{site_id}", "date": f"ge{since.isoformat()}"}),
    }


@router.get("/wards")
def wards(days: int = Query(28, ge=7, le=365)):
    """Triage view: every ward ranked by water exceedance and notification rise.

    This is the officer's working order -- what to look at first on a Tuesday
    morning -- rather than an alphabetical station list.
    """

    until = datetime.now(timezone.utc).date()
    since = (until - timedelta(days=days)).isoformat()
    gazetteer = registry()

    water_rows = _water(since=since)
    health_rows = _fetch(HEALTH_PROFILE, since=since)

    by_site_water: Dict[str, List[dict]] = defaultdict(list)
    for row in water_rows:
        by_site_water[row["site_id"]].append(row)
    by_site_health: Dict[str, List[dict]] = defaultdict(list)
    for row in health_rows:
        by_site_health[row["site_id"]].append(row)

    out = []
    for site_id, site in gazetteer.items():
        water = by_site_water.get(site_id, [])
        health = by_site_health.get(site_id, [])

        latest_by_indicator: Dict[str, dict] = {}
        for row in water:
            latest_by_indicator[row["indicator"]] = row
        exceedances = [e for e in (evaluate(r["indicator"], r["value"], r["unit"]) for r in latest_by_indicator.values()) if e]

        # Every latest reading, not only the failing ones: a severity matrix
        # needs to distinguish "within criteria" from "never measured", and an
        # exceedance-only list cannot.
        readings = {}
        for indicator, row in latest_by_indicator.items():
            exceedance = evaluate(indicator, row["value"], row["unit"])
            readings[indicator] = {
                "value": row["value"],
                "unit": row["unit"],
                "date": row["date"],
                "factor": (exceedance or {}).get("exceedance_factor"),
                "exceeds": exceedance is not None,
            }

        add = sorted([r for r in health if r["indicator"] == "acute_diarrhoeal_disease"], key=lambda r: r["when"] or "")
        rise = None
        if len(add) >= 2 and add[-2]["value"]:
            rise = round((add[-1]["value"] - add[-2]["value"]) / add[-2]["value"] * 100, 1)
        latest_add = add[-1] if add else None

        out.append(
            {
                "site_id": site_id,
                "name": site.name,
                "district": getattr(site, "district", None),
                "city": site.city,
                "reach": getattr(site, "reach", None),
                "latitude": site.latitude,
                "longitude": site.longitude,
                "water_readings": len(water),
                "readings": readings,
                "exceedances": exceedances,
                "severity": severity_of(exceedances),
                "cohort": latest_add["cohort"] if latest_add else None,
                "add_rate": latest_add["value"] if latest_add else None,
                "add_cases": latest_add["cases"] if latest_add else None,
                "add_baseline": latest_add["baseline"] if latest_add else None,
                "add_change_pct": rise,
                "co_located": bool(exceedances) and bool(rise and rise > 15),
            }
        )

    rank = {"HIGH": 0, "MODERATE": 1, "LOW": 2}
    out.sort(key=lambda w: (not w["co_located"], rank.get(w["severity"], 3), -(w["add_change_pct"] or 0)))
    return {
        "window_days": days,
        "since": since,
        "wards": out,
        "priority": [w["site_id"] for w in out if w["co_located"]],
        "fhir_server": base_url(),
    }


# ─────────────────────────── exports ───────────────────────────


@router.get("/export/readings.csv")
def export_readings(days: int = Query(28, ge=1, le=365), site_id: Optional[str] = None):
    """Water readings as CSV, for attaching to an incident record or a spreadsheet."""

    since = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    rows = _water(site_id=site_id, since=since)
    gazetteer = registry()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "site_id", "station", "district", "indicator", "value", "unit",
                     "threshold", "exceedance_factor", "basis", "observation_id"])
    for r in rows:
        site = gazetteer.get(r["site_id"])
        exceedance = evaluate(r["indicator"], r["value"], r["unit"]) or {}
        writer.writerow([
            r["date"], r["site_id"], site.name if site else "", getattr(site, "district", "") if site else "",
            r["indicator"], r["value"], r["unit"],
            exceedance.get("threshold", ""), exceedance.get("exceedance_factor", ""),
            exceedance.get("basis", ""), r["id"],
        ])
    buf.seek(0)
    name = f"oah-readings-{site_id or 'all'}-{days}d.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/surveillance.csv")
def export_surveillance(days: int = Query(90, ge=1, le=365)):
    """IDSP syndromic returns as CSV, with case counts and denominators intact."""

    since = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    rows = _fetch(HEALTH_PROFILE, since=since)
    gazetteer = registry()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "site_id", "station", "district", "cohort", "condition",
                     "cases", "population_at_risk", "rate_per_100k", "baseline_per_100k", "observation_id"])
    for r in rows:
        site = gazetteer.get(r["site_id"])
        writer.writerow([
            r["date"], r["site_id"], site.name if site else "", getattr(site, "district", "") if site else "",
            r["cohort"] or "", r["indicator"], r["cases"], r["population"], r["value"], r["baseline"], r["id"],
        ])
    buf.seek(0)
    name = f"oah-surveillance-{days}d.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/bundle.json")
def export_bundle(site_id: str = Query(...), days: int = Query(28, ge=1, le=365)):
    """A FHIR Bundle of the evidence for one station.

    This is the export that matters institutionally: ABDM mandates FHIR R4, so
    this attaches to an incident record natively rather than as a spreadsheet
    somebody has to retype.
    """

    since = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    params_w = {"_profile": BASE + WATER_PROFILE, "_tag": _tag(), "subject": f"Location/{site_id}",
                "date": f"ge{since}", "_count": "800"}
    params_c = {**params_w, "_profile": BASE + COMPONENT_PROFILE}
    params_h = {**params_w, "_profile": BASE + HEALTH_PROFILE}
    entries = []
    for params in (params_w, params_c, params_h):
        for resource in search("Observation", params):
            entries.append({"fullUrl": f"{base_url()}/Observation/{resource['id']}", "resource": resource})

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"tag": [{"system": TAG_SYSTEM, "code": dataset_tag()}]},
        "total": len(entries),
        "entry": entries,
    }
    name = f"oah-evidence-{site_id}-{days}d.json"
    return StreamingResponse(iter([json.dumps(bundle, indent=2)]), media_type="application/fhir+json",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ─────────────────────────── executive report ───────────────────────────


def _report_facts(days: int) -> dict:
    """Everything the brief asserts, derived here so the model cannot alter it."""

    data = wards(days=days)
    priority = [w for w in data["wards"] if w["co_located"]]
    worst = priority[0] if priority else (data["wards"][0] if data["wards"] else None)

    trends = {}
    if worst:
        for indicator in ("faecal_coliform", "dissolved_oxygen", "acute_diarrhoeal_disease"):
            try:
                trends[indicator] = trend(site_id=worst["site_id"], indicator=indicator, days=days)
            except Exception:
                continue

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "station_count": len(data["wards"]),
        "stations_with_exceedance": [w["site_id"] for w in data["wards"] if w["exceedances"]],
        "stations_co_located": data["priority"],
        "wards": data["wards"],
        "focus": worst,
        "trends": {k: {"change": v["change"], "latest": v["latest"], "unit": v["unit"],
                       "threshold": v["threshold"], "threshold_basis": v["threshold_basis"]}
                   for k, v in trends.items()},
        "caveat": (
            "Screening against CPCB bathing-water criteria and IS 10500:2012 reference values, not statutory "
            "enforcement limits. Water and syndromic measures co-located in a ward are an association to "
            "investigate; nothing here establishes that river condition caused the notified cases. "
            "Confirmatory sampling by the State Pollution Control Board is required before any attribution."
        ),
    }


@router.get("/report/facts")
def report_facts(days: int = Query(28, ge=7, le=365)):
    """The derived facts alone — no model call. Also the offline fallback."""

    return _report_facts(days)


REPORT_PROMPT = """You are drafting an executive situation report for a District Surveillance Officer in an \
IDSP/IHIP district surveillance unit in India. The reader is a medical officer who will act on it the same day.

You are given FACTS computed in Python from a HL7 FHIR repository. Do not recompute anything, do not introduce \
a number that is not in the facts, and do not soften or dramatize them.

Structure the report exactly as:

**Situation** — two or three sentences a Chief Medical Officer could act on.
**Key findings** — bullets, each naming its station, indicator and value, and the CPCB or IS 10500 criterion it \
is measured against.
**Recommended action** — concrete next steps in the officer's actual authority: confirmatory sampling request to \
the State Pollution Control Board, ward-level advisory, enhanced case finding, ORS depot activation, water sample \
collection from the affected ward's supply.
**Limitations** — state plainly what the data cannot show, using the caveat supplied.

Write in plain professional English. Co-location of a water exceedance and a rise in notifications is an \
association worth investigating, never evidence of causation — say so rather than implying otherwise."""


@router.get("/report")
def report(days: int = Query(28, ge=7, le=365)):
    """An executive brief: facts derived in Python, prose written by the model."""

    facts = _report_facts(days)
    try:
        from oah_agent.assistant import DEFAULT_MODEL, _client
    except ImportError:
        raise HTTPException(status_code=501, detail="oah-agent is not installed")

    import os

    try:
        client = _client()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            messages=[
                {"role": "system", "content": REPORT_PROMPT},
                {"role": "user", "content": f"FACTS:\n{json.dumps(facts, indent=2, default=str)}"},
            ],
        )
        narrative = response.choices[0].message.content or ""
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}")

    from oah_agent.grounding import check

    return {"narrative": narrative, "facts": facts, "grounding": check(narrative, [facts])}


@router.get("/panel", include_in_schema=False)
def panel():
    page = STATIC / "officer.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="officer.html is missing")
    return FileResponse(page, media_type="text/html")


# ─────────────────────────── studio: agent-orchestrated ───────────────────────────


@router.post("/studio/run")
def studio_run(body: dict):
    """Stream an investigation as it happens.

    Server-sent events rather than a single response: the officer should watch
    the reasoning and each chart arrive, not wait on a blank panel and receive a
    finished answer that appeared from nowhere.
    """

    from fastapi.responses import StreamingResponse

    question = (body or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")

    try:
        from oah_agent.studio import run
    except ImportError:
        raise HTTPException(status_code=501, detail="oah-agent is not installed")

    return StreamingResponse(
        run(question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/studio/report/{session_id}")
def studio_report(session_id: str):
    """The whole investigation as a self-contained HTML report.

    Not a summary written afterwards -- the transcript itself: the request, each
    reasoning step, every tool call with the queries it ran, the figures each
    returned, and the conclusion with its grounding verdict. That is what makes
    it attachable to an incident record: a reader can audit how the conclusion
    was reached, not just what it was.
    """

    try:
        from oah_agent.studio import session
    except ImportError:
        raise HTTPException(status_code=501, detail="oah-agent is not installed")

    data = session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="no such session; it may have expired with the process")

    def esc(value) -> str:
        return (
            str(value if value is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    blocks = []
    step_no = 0
    for entry in data["transcript"]:
        if entry["kind"] == "thinking":
            blocks.append(f'<div class="think"><div class="lbl">Reasoning</div><p>{esc(entry["text"])}</p></div>')
        elif entry["kind"] == "tool":
            step_no += 1
            args = ", ".join(f"{k}={v}" for k, v in (entry.get("arguments") or {}).items())
            urls = "".join(
                f'<div class="url"><a href="{esc(u)}">{esc(u)}</a></div>' for u in entry.get("urls") or []
            )
            # Only visualisation tools carry a render; building this line
            # unconditionally crashed on every data tool.
            render = entry.get("render")
            shown = ""
            if render:
                shown = f'<div class="shown">Rendered a <b>{esc(render["type"])}</b> view in the panel.'
                shown += f' {esc(render["caption"])}</div>' if render.get("caption") else "</div>"
            blocks.append(
                f'<div class="step"><div class="lbl">Action {step_no}</div>'
                f'<div class="tool">{esc(entry["tool"])}<span>({esc(args)})</span></div>'
                + (f'<div class="sum">{esc(entry["summary"])}</div>' if entry.get("summary") else "")
                + shown
                + (f'<div class="lbl2">Queries run</div>{urls}' if urls else "")
                + "</div>"
            )
        elif entry["kind"] == "answer":
            g = entry.get("grounding") or {}
            chip = (
                f'<span class="chip {"ok" if g.get("grounded") else "bad"}">'
                f'{"✓" if g.get("grounded") else "⚠"} '
                + (
                    f'Grounded — {g.get("figures_checked", 0)} figure(s) verified against '
                    f'{g.get("source_figure_count", 0)} retrieved'
                    if g.get("grounded")
                    else f'{len(g.get("unsupported_figures") or [])} figure(s) not found in the data'
                )
                + "</span>"
            )
            body_html = "".join(f"<p>{esc(p)}</p>" for p in (entry["text"] or "").split("\n\n") if p.strip())
            blocks.append(
                f'<div class="concl"><div class="lbl">Conclusion</div>{body_html}'
                f'<div class="ground">{chip}<span class="note">{esc(g.get("not_covered", ""))}</span></div></div>'
            )

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Investigation {esc(session_id)} — OneAquaHealth</title><style>
*{{box-sizing:border-box}}
body{{margin:0;padding:40px 24px 80px;background:#fff;color:#1D1D1F;
 font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif;
 letter-spacing:-.01em}}
.w{{max-width:760px;margin:0 auto}}
h1{{font-size:25px;font-weight:600;letter-spacing:-.022em;margin:0 0 6px}}
.meta{{color:#86868B;font-size:12.5px;margin-bottom:4px}}
.req{{background:#F0F7FF;border:1px solid #CCE4FF;border-radius:10px;padding:14px 16px;margin:20px 0 26px}}
.req .lbl{{color:#0071E3}}
.lbl{{font-size:10.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:#86868B;margin-bottom:5px}}
.lbl2{{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:#86868B;margin:10px 0 4px}}
.think{{border-left:2px solid #D2D2D7;padding:2px 0 2px 15px;margin:18px 0;color:#424245}}
.think p{{margin:0}}
.step{{border:1px solid #E8E8ED;border-radius:10px;padding:13px 15px;margin:14px 0;background:#FAFAFC}}
.tool{{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:13px;font-weight:500}}
.tool span{{color:#86868B;font-weight:400}}
.sum{{font-size:13.5px;color:#424245;margin-top:5px}}
.shown{{font-size:13px;color:#424245;margin-top:6px;padding:7px 10px;background:#fff;border-radius:7px;border:1px solid #E8E8ED}}
.url a{{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:#0071E3;word-break:break-all;text-decoration:none}}
.concl{{border-top:2px solid #1D1D1F;padding-top:18px;margin-top:30px}}
.concl p{{margin:0 0 11px}}
.ground{{margin-top:14px;padding-top:12px;border-top:1px solid #E8E8ED}}
.chip{{display:inline-block;font-size:12px;font-weight:500;padding:4px 11px;border-radius:99px;
 background:#E9F7E9;color:#0a7a0a;border:1px solid rgba(12,163,12,.25)}}
.chip.bad{{background:#FFEBEC;color:#d03b3b;border-color:rgba(208,59,59,.25)}}
.note{{display:block;font-size:12px;color:#86868B;margin-top:7px}}
footer{{margin-top:40px;padding-top:18px;border-top:1px solid #E8E8ED;font-size:11.5px;color:#86868B;line-height:1.6}}
@media print{{body{{padding:0}} .step{{break-inside:avoid}}}}
</style></head><body><div class="w">
<h1>District surveillance investigation</h1>
<div class="meta">Session {esc(session_id)} · {esc(data.get("started_at", ""))} · model {esc(data.get("model", ""))}</div>
<div class="meta">Repository: {esc(base_url())} · dataset tag {esc(dataset_tag())}</div>
<div class="req"><div class="lbl">Request</div>{esc(data["question"])}</div>
{"".join(blocks)}
<footer>
This report is the transcript of the investigation, not a summary written afterwards: every action the analyst
took is listed in the order it was taken, with the queries it ran. Figures were screened against CPCB Primary
Water Quality Criteria for Bathing Waters and IS 10500:2012 reference values — screening thresholds for a
prototype, not statutory enforcement limits; the Designated Best Use class for a reach is set by the State
Pollution Control Board. The readings in this deployment are synthetic demonstration data. Co-location of a
water exceedance and a rise in notifications is an association to investigate; nothing here establishes
causation, and confirmatory sampling is required before any attribution.
</footer></div></body></html>"""

    return StreamingResponse(
        iter([html]),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="investigation-{session_id}.html"'},
    )
