"""Environmental screening thresholds and the exceedance test.

These live in the ingestion package, not the agent package, because both need
them and ingestion sits lower in the dependency graph: `oah-agent` depends on
`oah-ingestion`, so a threshold owned by the agent is unreachable from the
pipeline that ingests the readings.

Every entry states its `basis`. A threshold with no stated provenance is a
number someone made up, and these are reported to public health officers.

These are SCREENING values for a prototype, not regulatory limits. Real
deployment values belong in the OAH IG's terminology, not in a Python dict.
"""

from __future__ import annotations

from typing import Dict, List, Optional

THRESHOLDS: Dict[str, dict] = {
    "nitrate": {
        "limit": 11.3,
        "unit": "mg/L",
        "direction": "above",
        "basis": "EU Drinking Water Directive 50 mg/L as NO3 ~= 11.3 mg/L as NO3-N; screening value only",
    },
    "ph": {
        "range": (6.5, 9.0),
        "unit": "pH",
        "direction": "outside",
        "basis": "EU Freshwater Fish Directive guideline band for cyprinid waters",
    },
    "zinc_dissolved": {
        "limit": 0.0078,
        "unit": "mg/L",
        "direction": "above",
        "basis": "EU WFD indicative freshwater bioavailable Zn EQS; screening value only",
    },
}


def evaluate(indicator: str, value: Optional[float], unit: Optional[str] = None) -> Optional[dict]:
    """Return an exceedance record, or None when within range / not screened.

    An indicator with no threshold is not an exceedance and not an error -- most
    OAH indicators (citizen survey codes, remote sensing indices) have no
    screening value, and that is expected.
    """

    rule = THRESHOLDS.get(indicator)
    if rule is None or value is None:
        return None

    if rule["direction"] == "above":
        if value <= rule["limit"]:
            return None
        return {
            "indicator": indicator,
            "value": value,
            "unit": unit or rule["unit"],
            "threshold": rule["limit"],
            "exceedance_factor": round(value / rule["limit"], 2),
            "basis": rule["basis"],
        }

    low, high = rule["range"]
    if low <= value <= high:
        return None
    return {
        "indicator": indicator,
        "value": value,
        "unit": unit or rule["unit"],
        "threshold": f"{low}-{high}",
        "basis": rule["basis"],
    }


def evaluate_many(readings: List[dict]) -> List[dict]:
    """Screen a list of `{indicator, value, unit}` dicts, keeping only exceedances."""

    found = []
    for reading in readings:
        result = evaluate(reading.get("indicator"), reading.get("value"), reading.get("unit"))
        if result is not None:
            found.append(result)
    return found


def as_reference() -> dict:
    """The threshold table in a form safe to hand to a language model."""

    reference = {}
    for indicator, rule in THRESHOLDS.items():
        reference[indicator] = {
            "unit": rule["unit"],
            "basis": rule["basis"],
            "rule": (
                f"exceedance when above {rule['limit']}"
                if rule["direction"] == "above"
                else f"exceedance when outside {rule['range'][0]}-{rule['range'][1]}"
            ),
        }
    return {
        "thresholds": reference,
        "note": (
            "Screening values for a prototype, not regulatory limits. "
            "Always quote the stated basis alongside the number."
        ),
    }
