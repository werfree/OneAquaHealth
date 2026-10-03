"""Water-quality screening thresholds and the exceedance test.

These live in the ingestion package, not the agent package, because both need
them and ingestion sits lower in the dependency graph: `oah-agent` depends on
`oah-ingestion`, so a threshold owned by the agent is unreachable from the
pipeline that ingests the readings.

Values follow the Indian regulatory position:

- **CPCB Primary Water Quality Criteria for Bathing Waters** (Designated Best
  Use Class B) for faecal coliform, BOD, dissolved oxygen and pH. These are the
  criteria a State Pollution Control Board reports a river reach against, and
  the ones a District Surveillance Officer will be challenged on.
- **IS 10500:2012** (Drinking Water Specification, BIS) for nitrate and
  ammoniacal nitrogen, used here as a reference point for raw surface water
  rather than as a compliance limit, since IS 10500 governs treated supply.

Every entry names its `basis`. A threshold with no stated provenance is a
number someone made up, and these reach public health officers.

They remain SCREENING values for a prototype. Statutory enforcement values and
the Designated Best Use class for a specific reach belong in the state PCB's
own notification, not in a Python dict.
"""

from __future__ import annotations

from typing import Dict, List, Optional

THRESHOLDS: Dict[str, dict] = {
    "faecal_coliform": {
        "limit": 2500.0,
        "unit": "MPN/100mL",
        "direction": "above",
        "basis": "CPCB Primary Water Quality Criteria for Bathing Waters — maximum permissible 2500 MPN/100mL (desirable 500)",
        "severity_at": 4.0,
    },
    "bod": {
        "limit": 3.0,
        "unit": "mg/L",
        "direction": "above",
        "basis": "CPCB Primary Water Quality Criteria for Bathing Waters — BOD (3 days, 27°C) 3 mg/L or less",
        "severity_at": 3.0,
    },
    "dissolved_oxygen": {
        "limit": 5.0,
        "unit": "mg/L",
        "direction": "below",
        "basis": "CPCB Primary Water Quality Criteria for Bathing Waters — dissolved oxygen 5 mg/L or more",
        "severity_at": 0.5,
    },
    "ph": {
        "range": (6.5, 8.5),
        "unit": "pH",
        "direction": "outside",
        "basis": "CPCB Primary Water Quality Criteria for Bathing Waters — pH between 6.5 and 8.5",
    },
    "nitrate": {
        "limit": 45.0,
        "unit": "mg/L",
        "direction": "above",
        "basis": "IS 10500:2012 acceptable limit 45 mg/L as NO3 — drinking water reference, not a surface-water compliance limit",
        "severity_at": 2.0,
    },
    "ammoniacal_nitrogen": {
        "limit": 1.2,
        "unit": "mg/L",
        "direction": "above",
        "basis": "CPCB advisory for raw water at drinking-water intakes — 1.2 mg/L as N",
        "severity_at": 3.0,
    },
    "chromium_total": {
        "limit": 0.05,
        "unit": "mg/L",
        "direction": "above",
        "basis": "IS 10500:2012 acceptable limit 0.05 mg/L as Cr — relevant to tannery-affected reaches",
        "severity_at": 4.0,
    },
}


def evaluate(indicator: str, value: Optional[float], unit: Optional[str] = None) -> Optional[dict]:
    """Return an exceedance record, or None when within criteria / not screened.

    An indicator with no threshold is not an exceedance and not an error — most
    OAH indicators (citizen survey codes, remote sensing indices) have no
    screening value, and that is expected.
    """

    rule = THRESHOLDS.get(indicator)
    if rule is None or value is None:
        return None

    base = {"indicator": indicator, "value": value, "unit": unit or rule["unit"], "basis": rule["basis"]}

    if rule["direction"] == "above":
        if value <= rule["limit"]:
            return None
        return {**base, "threshold": rule["limit"], "exceedance_factor": round(value / rule["limit"], 2)}

    if rule["direction"] == "below":
        # Dissolved oxygen fails by being too LOW; the ratio is inverted so a
        # bigger number still means "worse", consistent with every other row.
        if value >= rule["limit"]:
            return None
        return {
            **base,
            "threshold": rule["limit"],
            "exceedance_factor": round(rule["limit"] / value, 2) if value > 0 else None,
            "direction": "deficit",
        }

    low, high = rule["range"]
    if low <= value <= high:
        return None
    return {**base, "threshold": f"{low}-{high}"}


def evaluate_many(readings: List[dict]) -> List[dict]:
    """Screen a list of `{indicator, value, unit}` dicts, keeping only exceedances."""

    found = []
    for reading in readings:
        result = evaluate(reading.get("indicator"), reading.get("value"), reading.get("unit"))
        if result is not None:
            found.append(result)
    return found


def severity_of(exceedances: List[dict]) -> str:
    """HIGH when any reading is far past its criterion, else MODERATE.

    "Far past" is per-indicator (`severity_at`): four times the coliform
    criterion is a different kind of event from four times the BOD criterion,
    so a single global multiplier would misrank them.
    """

    for exceedance in exceedances:
        rule = THRESHOLDS.get(exceedance["indicator"], {})
        trigger = rule.get("severity_at")
        factor = exceedance.get("exceedance_factor")
        if trigger and factor and factor >= trigger:
            return "HIGH"
    return "MODERATE" if exceedances else "LOW"


def as_reference() -> dict:
    """The threshold table in a form safe to hand to a language model."""

    reference = {}
    for indicator, rule in THRESHOLDS.items():
        if rule["direction"] == "above":
            text = f"exceedance when above {rule['limit']} {rule['unit']}"
        elif rule["direction"] == "below":
            text = f"exceedance when below {rule['limit']} {rule['unit']}"
        else:
            text = f"exceedance when outside {rule['range'][0]}-{rule['range'][1]}"
        reference[indicator] = {"unit": rule["unit"], "basis": rule["basis"], "rule": text}
    return {
        "thresholds": reference,
        "note": (
            "CPCB bathing-water criteria and IS 10500:2012 reference values, applied as screening "
            "thresholds for a prototype. Not statutory enforcement limits; the Designated Best Use "
            "class for a specific reach is set by the State Pollution Control Board. "
            "Always quote the stated basis alongside the number."
        ),
    }
