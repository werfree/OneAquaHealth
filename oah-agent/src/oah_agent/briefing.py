"""Cross-domain One Health risk briefing.

Correlation is computed in Python, not by the language model. The model is used
only to write the narrative over numbers this module has already derived. That
split matters: an LLM asked to "find correlations" in a JSON blob will produce
confident arithmetic that nobody checked, and in a health context that is the
failure mode you least want.

What is computed here is deliberately modest and honestly labelled:
  - per-site exceedance of environmental thresholds
  - the cohort health/risk measures recorded at that same site
  - co-location of the two, reported as association, never causation

With a handful of readings per site there is no statistical power for anything
stronger, and the briefing says so rather than implying a trend.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .tools import get_cohort, get_site_profile, list_sites

logger = logging.getLogger("OAH_Briefing")

# Thresholds live in oah_ingestion.thresholds -- both the ingest-time alerting
# and this briefing screen against the same table, so an alert and a briefing
# can never disagree about what counts as an exceedance.
from oah_ingestion.thresholds import THRESHOLDS, evaluate_many  # noqa: E402

RISK_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


def _exceedances(environmental: List[dict]) -> List[dict]:
    """Screen observations, carrying each source Observation id into the finding."""

    findings = []
    for observation in environmental:
        for finding in evaluate_many([observation]):
            finding["observation_id"] = observation.get("id")
            findings.append(finding)
    return findings


def _interpretation(observation: dict) -> Optional[str]:
    """The agency's own LOW/MODERATE/HIGH reading, carried in the unit string."""

    unit = observation.get("unit") or ""
    for level in RISK_ORDER:
        if level in unit:
            return level
    return None


def site_briefing(site_id: str, dataset_tag: str = "oah-demo") -> dict:
    """Derive the full cross-domain picture for one site. No model involved."""

    profile = get_site_profile(site_id, dataset_tag=dataset_tag)
    environmental = profile["environmental_observations"]
    health = profile["health_observations"]

    exceedances = _exceedances(environmental)
    risks = [
        {
            "indicator": observation.get("indicator"),
            "score": observation.get("value"),
            "interpretation": _interpretation(observation),
            "cohort": observation.get("cohort"),
            "observation_id": observation.get("id"),
        }
        for observation in health
    ]
    elevated = [r for r in risks if RISK_ORDER.get(r["interpretation"] or "", 0) >= 1]

    cohorts = [get_cohort(group_id, dataset_tag=dataset_tag) for group_id in profile["cohorts"]]

    return {
        "site_id": site_id,
        "environmental_reading_count": len(environmental),
        "health_measure_count": len(health),
        "exceedances": exceedances,
        "risks": risks,
        "elevated_risks": elevated,
        "cohorts": [c for c in cohorts if "error" not in c],
        "co_location": bool(exceedances) and bool(elevated),
        "fhir_urls": profile["fhir_urls"],
        "caveat": (
            "Association only. These are co-located measurements from a prototype dataset with few readings "
            "per site; no temporal or statistical analysis has been performed and no causal claim is supported."
        ),
    }


def dataset_briefing(dataset_tag: str = "oah-demo") -> dict:
    """Run `site_briefing` across every site in the dataset."""

    sites = list_sites(dataset_tag=dataset_tag).get("sites", [])
    briefings = [site_briefing(site["site_id"], dataset_tag=dataset_tag) for site in sites]
    return {
        "site_count": len(briefings),
        "sites_with_exceedances": [b["site_id"] for b in briefings if b["exceedances"]],
        "sites_with_elevated_risk": [b["site_id"] for b in briefings if b["elevated_risks"]],
        "sites_with_co_location": [b["site_id"] for b in briefings if b["co_location"]],
        "briefings": briefings,
    }


NARRATIVE_PROMPT = """You are writing a One Health risk briefing for non-technical stakeholders \
(city environmental health officers).

You are given FACTS that were computed in Python from a HL7 FHIR repository. Do not recompute anything, \
do not add numbers that are not in the facts, and do not soften or dramatize them.

Write:
  1. A one-paragraph summary a city officer could act on.
  2. A short bulleted findings list, each citing its indicator and value.
  3. A "What this does not show" section that states the limits honestly, using the caveat provided.

Be direct. Co-location of an environmental exceedance and an elevated health risk score is an association \
worth investigating, never evidence of causation. Say that plainly rather than hinting at it."""


def narrate(facts: dict, *, model: Optional[str] = None) -> str:
    """Have the model write prose over already-computed facts."""

    import json
    import os

    from .assistant import DEFAULT_MODEL, _client

    client = _client()
    response = client.chat.completions.create(
        model=model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        messages=[
            {"role": "system", "content": NARRATIVE_PROMPT},
            {"role": "user", "content": f"FACTS:\n{json.dumps(facts, indent=2, default=str)}"},
        ],
    )
    return response.choices[0].message.content or ""
