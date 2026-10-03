"""FHIR query tools the assistant is allowed to call.

`docs/plan.md` describes the AI layer as a "Natural Language to FHIR Translator"
that emits FHIR REST URLs. This module deliberately does **not** do that. A
model that writes a search URL as free text can invent a search parameter that
does not exist, and FHIR servers answer an unknown parameter with an empty
bundle and HTTP 200 -- a wrong answer that is indistinguishable from "no data".

Instead the model picks a *typed tool* and supplies arguments. The code builds
the URL. An invalid code or site is then a Python-side error we can report,
never a silently empty result. Every tool returns the exact `fhir_url` it
called so any answer can be audited against the server by hand.

All queries are scoped to this pipeline's `meta.tag`, because the public HAPI
sandbox also holds OAH-profiled resources uploaded by other parties.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from oah_ingestion.fhir_client import FhirError, search, search_url
from oah_ingestion.sites import registry
from oah_models.fhir.resources import (
    OAH_DATASET_TAG_SYSTEM,
    OBSERVATION_HEALTH_MEASURE_PROFILE,
    OBSERVATION_INDICATORS_PROFILE,
    OBSERVATION_WITH_COMPONENT_PROFILE,
)

logger = logging.getLogger("OAH_Agent_Tools")

PROFILES = {
    "environmental_simple": OBSERVATION_INDICATORS_PROFILE,
    "environmental_component": OBSERVATION_WITH_COMPONENT_PROFILE,
    "health": OBSERVATION_HEALTH_MEASURE_PROFILE,
}


def _tag(dataset_tag: str = "oah-demo") -> str:
    return f"{OAH_DATASET_TAG_SYSTEM}|{dataset_tag}"


def _observation_value(obs: dict) -> Optional[float]:
    """Pull a comparable number out of any of the value shapes we emit."""

    if "valueQuantity" in obs:
        return obs["valueQuantity"].get("value")
    for component in obs.get("component", []):
        code = (component.get("code", {}).get("coding") or [{}])[0].get("code")
        if code in {"value", "average"} and "valueQuantity" in component:
            return component["valueQuantity"].get("value")
    return None


def _summarize(obs: dict) -> dict:
    """Compact an Observation to what a language model actually needs."""

    coding = (obs.get("code", {}).get("coding") or [{}])[0]
    value = _observation_value(obs)
    unit = (obs.get("valueQuantity") or {}).get("unit")
    if unit is None:
        for component in obs.get("component", []):
            if "valueQuantity" in component:
                unit = component["valueQuantity"].get("unit")
                break

    coded = obs.get("valueCodeableConcept") or {}
    coded_value = (coded.get("coding") or [{}])[0].get("code") or coded.get("text")

    summary = {
        "id": obs.get("id"),
        "indicator": coding.get("code"),
        "site": (obs.get("subject", {}).get("reference") or "").replace("Location/", "") or None,
        "when": obs.get("effectiveDateTime") or obs.get("effectivePeriod", {}).get("start"),
    }
    if value is not None:
        summary["value"] = value
        summary["unit"] = unit
    if coded_value:
        summary["coded_value"] = coded_value
    if obs.get("focus"):
        summary["cohort"] = obs["focus"][0].get("reference", "").replace("Group/", "")
    components = [
        {
            "stat": (c.get("code", {}).get("coding") or [{}])[0].get("code"),
            "value": (c.get("valueQuantity") or {}).get("value"),
        }
        for c in obs.get("component", [])
    ]
    if len(components) > 1:
        summary["statistics"] = components
    return summary


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def list_sites(dataset_tag: str = "oah-demo") -> dict:
    """Which monitoring sites exist, and what has been observed at each."""

    params = {"_tag": _tag(dataset_tag), "_count": "200"}
    try:
        locations = search("Location", params)
    except FhirError as exc:
        return {"error": str(exc), "fhir_url": search_url("Location", params)}

    gazetteer = registry()
    sites = []
    for location in locations:
        site_id = location.get("id")
        known = gazetteer.get(site_id)
        position = location.get("position") or {}
        sites.append(
            {
                "site_id": site_id,
                "name": location.get("name"),
                "city": known.city if known else None,
                "latitude": position.get("latitude"),
                "longitude": position.get("longitude"),
            }
        )
    return {"sites": sites, "count": len(sites), "fhir_url": search_url("Location", params)}


def search_observations(
    kind: str = "environmental_simple",
    indicator: Optional[str] = None,
    site_id: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50,
    dataset_tag: str = "oah-demo",
) -> dict:
    """Search Observations by OAH profile, indicator code, site, and value range.

    `since`/`until` are ISO dates (YYYY-MM-DD) bounding `Observation.effective[x]`.

    `kind` selects the OAH profile: `environmental_simple`
    (observation-indicators-oah -- single readings and citizen survey answers),
    `environmental_component` (observation-with-component-oah -- readings with
    avg/min/max statistics), or `health` (observation-health-measure-oah --
    cohort health and risk measures).
    """

    profile = PROFILES.get(kind)
    if profile is None:
        return {"error": f"kind must be one of {sorted(PROFILES)}; got {kind!r}"}

    params: Dict[str, str] = {"_profile": profile, "_tag": _tag(dataset_tag), "_count": str(min(limit, 200))}
    if indicator:
        params["code"] = indicator
    if site_id:
        params["subject"] = f"Location/{site_id}"
    # FHIR `date` accepts repeated prefixed values, which urlencode cannot
    # express as one key; the client joins them with a comma and the server
    # reads that as AND.
    bounds = []
    if since:
        bounds.append(f"ge{since}")
    if until:
        bounds.append(f"le{until}")
    if bounds:
        params["date"] = ",".join(bounds)
    params["_sort"] = "date"

    url = search_url("Observation", params)
    try:
        raw = search("Observation", params)
    except FhirError as exc:
        return {"error": str(exc), "fhir_url": url}

    results = [_summarize(o) for o in raw]
    # Value filtering is applied client-side: the readings that carry summary
    # statistics hold their number in `component`, which the FHIR `value-quantity`
    # search parameter does not reach.
    if min_value is not None:
        results = [r for r in results if r.get("value") is not None and r["value"] >= min_value]
    if max_value is not None:
        results = [r for r in results if r.get("value") is not None and r["value"] <= max_value]

    return {"observations": results[:limit], "count": len(results), "fhir_url": url}


def get_site_profile(site_id: str, dataset_tag: str = "oah-demo") -> dict:
    """Everything known about one site: environment, health measures, cohort.

    This is the One Health join -- it is the single call that puts a stream's
    chemistry next to the health of the population living beside it.
    """

    environmental: List[dict] = []
    urls = []
    for kind in ("environmental_simple", "environmental_component"):
        result = search_observations(kind=kind, site_id=site_id, limit=200, dataset_tag=dataset_tag)
        environmental.extend(result.get("observations", []))
        urls.append(result.get("fhir_url"))

    health_result = search_observations(kind="health", site_id=site_id, limit=200, dataset_tag=dataset_tag)
    urls.append(health_result.get("fhir_url"))

    cohorts = sorted({o["cohort"] for o in health_result.get("observations", []) if o.get("cohort")})

    return {
        "site_id": site_id,
        "environmental_observations": environmental,
        "health_observations": health_result.get("observations", []),
        "cohorts": cohorts,
        "fhir_urls": urls,
    }


def get_cohort(group_id: str, dataset_tag: str = "oah-demo") -> dict:
    """The demographic definition behind a cohort referenced by a health measure."""

    params = {"_tag": _tag(dataset_tag), "_id": group_id}
    url = search_url("Group", params)
    try:
        groups = search("Group", params)
    except FhirError as exc:
        return {"error": str(exc), "fhir_url": url}
    if not groups:
        return {"error": f"no Group {group_id!r} in this dataset", "fhir_url": url}

    group = groups[0]
    characteristics = {}
    for characteristic in group.get("characteristic", []):
        key = (characteristic.get("code", {}).get("coding") or [{}])[0].get("code")
        if "valueRange" in characteristic:
            low = characteristic["valueRange"].get("low", {}).get("value")
            high = characteristic["valueRange"].get("high", {}).get("value")
            characteristics[key] = f"{low}-{high}"
        elif "valueCodeableConcept" in characteristic:
            characteristics[key] = characteristic["valueCodeableConcept"].get("text")
        elif "valueReference" in characteristic:
            characteristics[key] = characteristic["valueReference"].get("reference")

    return {"group_id": group.get("id"), "name": group.get("name"), "characteristics": characteristics, "fhir_url": url}


def get_thresholds() -> dict:
    """The screening thresholds this project evaluates exceedances against.

    Exposed as a tool so the assistant quotes a real, sourced value instead of
    inventing a "safe level" -- a model asked about exceedance will otherwise
    supply a plausible number from memory, which in a health context is the
    worst possible failure mode. Shared with ingest-time alerting, so the
    assistant and an alert can never disagree about what counts as elevated.
    """

    from oah_ingestion.thresholds import as_reference

    return as_reference()


# ---------------------------------------------------------------------------
# OpenAI tool schemas
# ---------------------------------------------------------------------------

TOOL_IMPLEMENTATIONS = {
    "get_thresholds": get_thresholds,
    "list_sites": list_sites,
    "search_observations": search_observations,
    "get_site_profile": get_site_profile,
    "get_cohort": get_cohort,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_thresholds",
            "description": (
                "Get the screening thresholds used to judge whether an environmental reading is elevated, with the "
                "regulatory basis for each. You MUST call this before describing any value as safe, unsafe, high, or "
                "exceeding a limit. Never state a threshold from your own knowledge."
            ),
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sites",
            "description": "List every monitoring site in the OAH dataset with its city and GPS position. Call this first when you do not know which site the user means.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_observations",
            "description": (
                "Search OAH Observations on the FHIR server. Use kind='environmental_simple' for single sensor "
                "readings and citizen-survey answers, kind='environmental_component' for readings that carry "
                "average/minimum/maximum statistics, and kind='health' for population health and risk measures. "
                "Use since/until to ask whether something CHANGED rather than what it is now. "
                "Indicator codes in this dataset: faecal_coliform, bod, dissolved_oxygen, ph, "
                "ammoniacal_nitrogen, chromium_total (water, CPCB parameters); "
                "acute_diarrhoeal_disease, enteric_fever, viral_hepatitis_a_e, cholera (IDSP syndromic, health)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["environmental_simple", "environmental_component", "health"],
                        "description": "Which OAH Observation profile to search.",
                    },
                    "indicator": {"type": "string", "description": "Indicator code, e.g. 'nitrate' or 'pathogen_risk'."},
                    "site_id": {"type": "string", "description": "Restrict to one site, e.g. 'site-c1-mondego'."},
                    "min_value": {"type": "number", "description": "Only return readings at or above this value."},
                    "max_value": {"type": "number", "description": "Only return readings at or below this value."},
                    "since": {"type": "string", "description": "Only readings on or after this ISO date, e.g. '2026-09-20'."},
                    "until": {"type": "string", "description": "Only readings on or before this ISO date."},
                    "limit": {"type": "integer", "description": "Maximum results (default 50)."},
                },
                "required": ["kind"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_site_profile",
            "description": (
                "Get everything recorded at one site in a single call: environmental readings, population health "
                "measures, and the cohorts those measures describe. Use this for any question that relates stream "
                "condition to human health -- it is the cross-domain One Health join."
            ),
            "parameters": {
                "type": "object",
                "properties": {"site_id": {"type": "string", "description": "Site id, e.g. 'site-coimbra-t1'."}},
                "required": ["site_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cohort",
            "description": "Look up the demographic definition (age range, sex, location) of a cohort Group referenced by a health measure.",
            "parameters": {
                "type": "object",
                "properties": {"group_id": {"type": "string", "description": "Group id, e.g. 'group-coimbra-adults-18-64'."}},
                "required": ["group_id"],
                "additionalProperties": False,
            },
        },
    },
]
