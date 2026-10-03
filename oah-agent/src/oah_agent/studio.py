"""An orchestrating analyst: one request in, a worked investigation out.

The earlier panel was a wizard -- five numbered stages the officer clicked
through in order. That put the human in charge of navigation and the machine in
charge of nothing, which is backwards for a system that has a reasoning model in
it. Here the officer states an intent and the model decides what to do: which
data to pull, which comparison to make, and **which visualisation actually
answers the question**.

The key move is that charts are tools. `show_trend`, `show_matrix`,
`show_ranking` and `show_scatter` sit in the same tool list as
`search_observations`, so choosing a scatter over a timeline is a decision the
model makes about the question in front of it, not a panel someone pre-placed on
a dashboard. A visualisation tool returns a spec; the browser draws it.

Everything the run does is streamed as it happens -- the plan, each tool call
with why it was made, each result, each chart -- so the panel fills in step by
step and the officer can see the reasoning rather than a finished answer that
appeared from nowhere. The same transcript is what gets written out as the
downloadable report, so the report is a record of the actual investigation
rather than a summary composed afterwards.

Two rules hold from the rest of the project: the model never writes a FHIR query
(it picks a typed tool and the code builds the URL), and every figure in the
final answer is checked against the data the tools returned.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional

from . import grounding
from .tools import TOOL_IMPLEMENTATIONS, TOOL_SCHEMAS

logger = logging.getLogger("OAH_Studio")

DEFAULT_MODEL = "gpt-4o"
MAX_ROUNDS = 10

# Sessions live in memory: a run is short, and its only consumer is the report
# download that follows it. Nothing here should outlive the process.
SESSIONS: Dict[str, dict] = {}


# ───────────────────────────── analysis tools ─────────────────────────────


def _officer():
    from oah_ingestion import officer

    return officer


def rank_wards(days: int = 28) -> dict:
    """Every ward screened and ranked, with its exceedances and case change."""

    data = _officer().wards(days=days)
    exceeding = [w for w in data["wards"] if w["exceedances"]]
    return {
        "window_days": days,
        "summary": (
            f"{len(data['wards'])} wards screened over {days} days; {len(exceeding)} exceed a criterion; "
            f"co-located (water and rising cases): {data['priority'] or 'none'}"
        ),
        "fhir_urls": [data.get("fhir_server", "") + "/Observation?_tag=…|oah-demo"],
        "priority": data["priority"],
        "wards": [
            {
                "site_id": w["site_id"],
                "name": w["name"],
                "district": w["district"],
                "severity": w["severity"],
                "exceedances": [
                    {"indicator": e["indicator"], "value": e["value"], "unit": e["unit"],
                     "factor": e.get("exceedance_factor"), "threshold": e.get("threshold")}
                    for e in w["exceedances"]
                ],
                "add_change_pct": w["add_change_pct"],
                "add_cases": w["add_cases"],
                "cohort": w["cohort"],
                "co_located": w["co_located"],
            }
            for w in data["wards"]
        ],
    }


def get_trend(site_id: str, indicator: str, days: int = 28) -> dict:
    """The series for one indicator at one station, with the change computed."""

    t = _officer().trend(site_id=site_id, indicator=indicator, days=days)
    return {
        "site_id": site_id, "indicator": indicator, "unit": t["unit"],
        "points": t["points"], "latest": t["latest"], "change": t["change"],
        "threshold": t["threshold"], "threshold_basis": t["threshold_basis"],
        "series": t["series"], "fhir_url": t["fhir_url"],
    }


# ───────────────────────────── visualisation tools ─────────────────────────
# Each returns a spec the browser draws. The model picks the form; the point of
# putting them in the tool list is that "which chart answers this" becomes a
# reasoning step rather than a layout decision made in advance.


def show_stats(items: List[dict], caption: str = "") -> dict:
    """Headline figures. Use for counts and standings, never for a comparison."""

    return {"_render": {"type": "stats", "items": items[:6], "caption": caption}}


def show_matrix(days: int = 28, caption: str = "") -> dict:
    """Station × indicator grid shaded by how far past its criterion each sits.

    Use when the question is "where is everything bad at once" across the whole
    district -- it is the only form that shows every station and every indicator
    in one frame.
    """

    data = _officer().wards(days=days)
    rows = [
        {"site_id": w["site_id"], "name": w["name"], "readings": w["readings"],
         "add_change_pct": w["add_change_pct"]}
        for w in data["wards"]
    ]
    indicators = sorted({i for r in rows for i in (r["readings"] or {})})
    return {"_render": {"type": "matrix", "rows": rows, "indicators": indicators, "caption": caption},
            "summary": f"{len(rows)} stations × {len(indicators)} indicators"}


def show_ranking(days: int = 28, caption: str = "") -> dict:
    """Wards ranked by worst exceedance, with case change alongside.

    Use to establish working order -- what to look at first.
    """

    data = rank_wards(days=days)
    return {"_render": {"type": "ranking", "wards": data["wards"], "caption": caption},
            "summary": f"{len(data['wards'])} wards ranked; priority: {data['priority'] or 'none'}"}


def show_trend(site_id: str, indicator: str, days: int = 28, caption: str = "") -> dict:
    """Two aligned panels on one time axis: this indicator above, notified ADD below.

    Use when the question is about change over time at one station, or about
    whether water moved *before* cases did. The lag between the two peaks is the
    thing worth seeing, which a single-series chart cannot show.
    """

    water = get_trend(site_id, indicator, days)
    health = get_trend(site_id, "acute_diarrhoeal_disease", days)
    return {
        "_render": {"type": "trend", "water": water, "health": health, "caption": caption},
        "summary": (
            f"{indicator} at {site_id}: {water['points']} points, latest {water['latest']} "
            f"{water['unit'] or ''}, change {(water['change'] or {}).get('pct')}%; "
            f"ADD change {(health['change'] or {}).get('pct')}%"
        ),
        "fhir_urls": [water["fhir_url"], health["fhir_url"]],
    }


def show_scatter(days: int = 28, caption: str = "") -> dict:
    """Every ward plotted: worst exceedance against change in notifications.

    Use to compare wards against each other -- it is the form that reveals a
    station with bad water but no case rise, which no single-ward view shows.
    """

    data = rank_wards(days=days)
    return {"_render": {"type": "scatter", "wards": data["wards"], "caption": caption},
            "summary": f"{len(data['wards'])} wards plotted; priority: {data['priority'] or 'none'}"}


STUDIO_IMPLEMENTATIONS = {
    **TOOL_IMPLEMENTATIONS,
    "rank_wards": rank_wards,
    "get_trend": get_trend,
    "show_stats": show_stats,
    "show_matrix": show_matrix,
    "show_ranking": show_ranking,
    "show_trend": show_trend,
    "show_scatter": show_scatter,
}

_D = {"type": "integer", "description": "Window in days (default 28)."}
_C = {"type": "string", "description": "One short sentence saying what this shows and why you chose it."}

STUDIO_SCHEMAS = TOOL_SCHEMAS + [
    {"type": "function", "function": {
        "name": "rank_wards",
        "description": "Screen every ward and rank it: exceedances with their criteria, change in notified acute diarrhoeal disease, and whether the two co-occur. The usual first call for any district-wide question.",
        "parameters": {"type": "object", "properties": {"days": _D}, "required": [], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_trend",
        "description": "The numeric series for one indicator at one station over time, with the change against the preceding period already computed. Use when you need the numbers; use show_trend when the officer should see them.",
        "parameters": {"type": "object", "properties": {
            "site_id": {"type": "string"}, "indicator": {"type": "string"}, "days": _D},
            "required": ["site_id", "indicator"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "show_stats",
        "description": "Display headline figures in the panel. For counts and standings only — never for a comparison, which needs a chart.",
        "parameters": {"type": "object", "properties": {
            "items": {"type": "array", "description": "2-6 figures",
                      "items": {"type": "object", "properties": {
                          "label": {"type": "string"}, "value": {"type": "string"},
                          "detail": {"type": "string"}, "alarm": {"type": "boolean"}},
                          "required": ["label", "value"], "additionalProperties": False}},
            "caption": _C}, "required": ["items"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "show_matrix",
        "description": "Display a station × indicator severity grid. The only form showing every station and indicator at once — use for 'where is everything bad'.",
        "parameters": {"type": "object", "properties": {"days": _D, "caption": _C}, "required": [], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "show_ranking",
        "description": "Display wards ranked by worst exceedance with case change alongside. Use to establish what to work first.",
        "parameters": {"type": "object", "properties": {"days": _D, "caption": _C}, "required": [], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "show_trend",
        "description": "Display two aligned panels on one time axis — the chosen water indicator above, notified ADD below. Use for change over time at one station, and to show whether water moved before cases did.",
        "parameters": {"type": "object", "properties": {
            "site_id": {"type": "string"}, "indicator": {"type": "string", "description": "e.g. faecal_coliform, bod, dissolved_oxygen"},
            "days": _D, "caption": _C}, "required": ["site_id", "indicator"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "show_scatter",
        "description": "Display every ward as a point: worst exceedance against change in notifications. Use to compare wards and to surface a station with bad water but no case rise.",
        "parameters": {"type": "object", "properties": {"days": _D, "caption": _C}, "required": [], "additionalProperties": False}}},
]


SYSTEM = """You are the district surveillance analyst for a District Surveillance Officer in an IDSP/IHIP \
unit in India. The officer gives you an intent; you run the investigation and show your work.

The repository holds, as HL7 FHIR R4 conforming to the OneAquaHealth IG:
  - water quality readings from CPCB/state-PCB stations (faecal_coliform, bod, dissolved_oxygen, ph, \
ammoniacal_nitrogen, chromium_total)
  - IDSP syndromic returns per ward cohort (acute_diarrhoeal_disease, enteric_fever, viral_hepatitis_a_e, cholera)

How to work:
1. Start by saying, in one or two sentences, what you are going to do and why. Then do it.
2. Call tools. You decide which and in what order — there is no fixed sequence.
3. **Show the officer what you found.** A `show_*` tool renders into their panel. Pick the form that answers \
the question: show_matrix for "where is everything bad", show_ranking for working order, show_trend for change \
over time and for lag, show_scatter to compare wards against each other, show_stats for plain counts. Always \
pass a caption saying what it shows and why you chose that form.
4. Prefer two or three well-chosen views over many. A chart that does not answer the question is clutter.
5. Finish with a short written conclusion and a recommended action in the officer's actual authority: \
confirmatory sampling request to the State Pollution Control Board, ward-level advisory, enhanced case finding, \
ORS depot activation, water sampling from the ward supply.

Rules you must not break:
- Never state a number you did not get from a tool. If the data is not there, say so.
- Thresholds are numbers too. Call get_thresholds before describing anything as safe, high or exceeding, and \
quote the basis it returns. A filter value you chose is not a threshold.
- Do not write URLs. The harness records every query and shows it to the officer.
- Co-location of a water exceedance and a rise in notifications is an association worth investigating, never \
evidence of causation. Say so plainly.
- This is a prototype dataset. Do not describe a single reading as a trend."""


def _client():
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The studio needs the OpenAI SDK: pip install openai") from exc
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env or export it.")
    return OpenAI()


def _event(kind: str, **payload) -> str:
    return f"data: {json.dumps({'type': kind, **payload}, default=str)}\n\n"


def run(question: str, *, model: Optional[str] = None) -> Iterator[str]:
    """Run an investigation, yielding SSE events as each step happens."""

    session_id = uuid.uuid4().hex[:12]
    model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    transcript: List[dict] = []
    results: List[object] = []

    SESSIONS[session_id] = {
        "id": session_id, "question": question, "model": model,
        "started_at": datetime.now(timezone.utc).isoformat(), "transcript": transcript,
    }
    yield _event("start", session=session_id, question=question, model=model)

    try:
        client = _client()
    except RuntimeError as exc:
        yield _event("error", message=str(exc))
        return

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]

    try:
        for _ in range(MAX_ROUNDS):
            response = client.chat.completions.create(
                model=model, messages=messages, tools=STUDIO_SCHEMAS, tool_choice="auto"
            )
            choice = response.choices[0].message
            messages.append(choice.model_dump(exclude_none=True))

            # Narration between tool calls is the model's reasoning; show it.
            if choice.content:
                transcript.append({"kind": "thinking", "text": choice.content})
                yield _event("thinking", text=choice.content)

            if not choice.tool_calls:
                verdict = grounding.check(choice.content or "", results)
                transcript.append({"kind": "answer", "text": choice.content or "", "grounding": verdict})
                SESSIONS[session_id]["grounding"] = verdict
                SESSIONS[session_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
                yield _event("answer", text=choice.content or "", grounding=verdict)
                yield _event("done", session=session_id)
                return

            for call in choice.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                yield _event("tool_start", tool=name, arguments=args)

                implementation = STUDIO_IMPLEMENTATIONS.get(name)
                if implementation is None:
                    result = {"error": f"unknown tool {name!r}"}
                else:
                    try:
                        result = implementation(**args)
                    except Exception as exc:
                        logger.exception("Tool %s failed", name)
                        result = {"error": f"{type(exc).__name__}: {exc}"}

                render = result.pop("_render", None) if isinstance(result, dict) else None
                results.append(result)

                urls = []
                if isinstance(result, dict):
                    urls = result.get("fhir_urls") or ([result["fhir_url"]] if result.get("fhir_url") else [])

                step = {"kind": "tool", "tool": name, "arguments": args,
                        "summary": (result or {}).get("summary") if isinstance(result, dict) else None,
                        "urls": [u for u in urls if u], "render": render}
                transcript.append(step)
                yield _event("tool_done", tool=name, summary=step["summary"], urls=step["urls"])
                if render:
                    yield _event("render", tool=name, spec=render)

                # The model sees the data, not the chart spec -- a render blob
                # would waste its context describing pixels it cannot read.
                payload = result if render is None else {"rendered": render["type"],
                                                         "summary": step["summary"], "ok": True}
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(payload, default=str)[:12000]})

        yield _event("error", message="Stopped after the maximum number of rounds.")
    except Exception as exc:
        logger.exception("Studio run failed")
        yield _event("error", message=f"{type(exc).__name__}: {exc}")


def session(session_id: str) -> Optional[dict]:
    return SESSIONS.get(session_id)
