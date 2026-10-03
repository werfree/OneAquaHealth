"""Generate a 28-day demonstration series across the Indian pilot stations.

Why this exists: every earlier sample was a single day, so the question a
District Surveillance Officer actually asks -- "has anything *changed* at the
stations near this ward?" -- could not be answered at all. A trend needs a
series.

THE READINGS ARE SYNTHETIC. They are shaped to be plausible against CPCB's
reported picture of these reaches (Yamuna heavily degraded through Delhi,
recovering upstream at Wazirabad; Jajmau carrying tannery chromium) and to
contain one deliberate, discoverable event: a sewage-pumping failure at ITO on
day 18 that drives faecal coliform up, dissolved oxygen down, and is followed
about a week later by a rise in acute diarrhoeal disease in the catchment ward.

That lag is the point. It is what makes the cross-domain join worth making,
and what gives the officer something to reason about rather than a static
snapshot. It is demonstration data and must not be presented as observation.

    python3 demo/generate_timeseries.py            # writes demo/timeseries/
    python3 demo/generate_timeseries.py --ingest   # also runs them through the pipeline
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "timeseries"

DAYS = 28
EVENT_DAY = 18          # sewage pumping failure at ITO
HEALTH_LAG = 7          # ADD cases rise about a week after exposure

# Per-station baselines. Loosely tracks CPCB's reported picture of these
# reaches; the numbers are synthetic.
STATIONS = {
    "yam-wazirabad": {
        "city": "delhi", "device": "CPCB-DL-WZB-01",
        "base": {"faecal_coliform": 900, "bod": 2.4, "dissolved_oxygen": 6.8, "ph": 7.6,
                 "ammoniacal_nitrogen": 0.6},
    },
    "yam-ito": {
        "city": "delhi", "device": "CPCB-DL-ITO-01",
        "base": {"faecal_coliform": 21000, "bod": 11.0, "dissolved_oxygen": 2.1, "ph": 7.4,
                 "ammoniacal_nitrogen": 4.2},
        "event": True,
    },
    "yam-okhla": {
        "city": "delhi", "device": "CPCB-DL-OKH-01",
        "base": {"faecal_coliform": 34000, "bod": 14.5, "dissolved_oxygen": 1.4, "ph": 7.3,
                 "ammoniacal_nitrogen": 5.8},
    },
    "gan-jajmau": {
        "city": "kanpur", "device": "UPPCB-KNP-JAJ-01",
        "base": {"faecal_coliform": 7800, "bod": 6.2, "dissolved_oxygen": 4.4, "ph": 7.9,
                 "chromium_total": 0.11},
    },
    "gan-assi": {
        "city": "varanasi", "device": "UPPCB-VNS-ASI-01",
        "base": {"faecal_coliform": 3100, "bod": 3.4, "dissolved_oxygen": 5.9, "ph": 8.0},
    },
    "mit-dharavi": {
        "city": "mumbai", "device": "MPCB-MUM-MIT-01",
        "base": {"faecal_coliform": 16000, "bod": 9.1, "dissolved_oxygen": 2.6, "ph": 7.2,
                 "ammoniacal_nitrogen": 3.1},
    },
}

UNITS = {
    "faecal_coliform": "MPN/100mL", "bod": "mg/L", "dissolved_oxygen": "mg/L",
    "ph": "pH", "ammoniacal_nitrogen": "mg/L", "chromium_total": "mg/L",
}

# Cohorts: the ward population served by each reach.
COHORTS = {
    "yam-ito": ("ward-delhi-central-riverside", "Central Delhi riverside wards", 412_000),
    "yam-okhla": ("ward-delhi-se-riverside", "South East Delhi riverside wards", 388_000),
    "yam-wazirabad": ("ward-delhi-north-riverside", "North Delhi riverside wards", 265_000),
    "gan-jajmau": ("ward-kanpur-jajmau", "Jajmau and adjoining wards", 198_000),
    "gan-assi": ("ward-varanasi-ghats", "Varanasi ghat-side wards", 142_000),
    "mit-dharavi": ("ward-mumbai-dharavi", "Dharavi and Mahim catchment", 630_000),
}

# IDSP syndromic categories that are plausibly water-associated.
CONDITIONS = {
    "acute_diarrhoeal_disease": 24.0,
    "enteric_fever": 6.5,
    "viral_hepatitis_a_e": 3.2,
    "cholera": 0.4,
}


def event_multiplier(station: dict, day: int) -> float:
    """A pumping failure on EVENT_DAY, decaying over roughly a week."""

    if not station.get("event") or day < EVENT_DAY:
        return 1.0
    return 1.0 + 3.4 * math.exp(-(day - EVENT_DAY) / 3.0)


def water_event(site_id: str, station: dict, day: int, start: datetime) -> dict:
    rng = random.Random(f"{site_id}-{day}")
    when = start + timedelta(days=day, hours=9)
    mult = event_multiplier(station, day)

    measurements = []
    for parameter, base in station["base"].items():
        noise = 1 + rng.uniform(-0.12, 0.12)
        if parameter == "faecal_coliform":
            value = base * noise * mult
        elif parameter == "dissolved_oxygen":
            value = base * noise / (mult ** 0.6)        # DO falls as load rises
        elif parameter in {"bod", "ammoniacal_nitrogen"}:
            value = base * noise * (1 + (mult - 1) * 0.5)
        else:
            value = base * noise
        value = round(value, 2 if value < 100 else 0)
        measurements.append({"parameter": parameter, "unit": UNITS[parameter], "value": value})

    return {
        "source_type": "IOT_TELEMETRY",
        "city": station["city"],
        "site_id": site_id,
        "timestamp": when.isoformat().replace("+00:00", "Z"),
        "payload": {"device_id": station["device"], "measurements": measurements},
    }


def health_event(site_id: str, station: dict, day: int, start: datetime) -> dict:
    """Weekly IDSP return for the ward served by this reach."""

    group_id, group_name, population = COHORTS[site_id]
    rng = random.Random(f"{site_id}-health-{day}")
    when = start + timedelta(days=day, hours=17)

    # Load at this station scales the baseline; a pumping failure shows up in
    # the ward's ADD count about a week later.
    load = station["base"]["faecal_coliform"] / 2500.0
    lagged = event_multiplier(station, day - HEALTH_LAG)

    lines = []
    for condition, national_base in CONDITIONS.items():
        baseline = national_base * (1 + 0.12 * math.log10(max(load, 1.0)))
        factor = lagged if condition in {"acute_diarrhoeal_disease", "cholera"} else 1.0
        rate = baseline * factor * (1 + rng.uniform(-0.1, 0.1))
        cases = max(0, round(rate * population / 100_000))
        lines.append(
            {
                "condition": condition,
                "cases": cases,
                "population_at_risk": population,
                "baseline_rate_per_100k": round(baseline, 2),
            }
        )

    return {
        "source_type": "PUBLIC_HEALTH",
        "city": station["city"],
        "site_id": site_id,
        "timestamp": when.isoformat().replace("+00:00", "Z"),
        "payload": {
            "health_agency": "IDSP_District_Surveillance_Unit",
            "evaluation_period": f"week ending {(when).date().isoformat()}",
            "cohort": {"group_id": group_id, "age_range": "0-99", "gender": "all"},
            "disease_surveillance": lines,
        },
    }


def build(days: int = DAYS) -> list:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    events = []
    for day in range(days):
        for site_id, station in STATIONS.items():
            events.append(water_event(site_id, station, day, start))
            if day % 7 == 6:                      # weekly IDSP return
                events.append(health_event(site_id, station, day, start))
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=DAYS)
    parser.add_argument("--ingest", action="store_true", help="run the events through the real pipeline")
    args = parser.parse_args()

    events = build(args.days)
    OUT.mkdir(exist_ok=True)
    (OUT / "events.json").write_text(json.dumps(events, indent=1), encoding="utf-8")
    water = sum(1 for e in events if e["source_type"] == "IOT_TELEMETRY")
    print(f"{len(events)} events over {args.days} days ({water} water, {len(events)-water} surveillance)")
    print(f"written to {OUT/'events.json'}")

    if not args.ingest:
        print("\nre-run with --ingest to push them through the pipeline to FHIR")
        return

    sys.path.insert(0, str(HERE.parent / "oah-ingestion" / "src"))
    sys.path.insert(0, str(HERE.parent / "oah-pydantic-models" / "src"))
    import logging

    from pydantic import TypeAdapter

    from oah_ingestion.envelope import IngestionEnvelope
    from oah_ingestion.pipeline import process

    logging.disable(logging.INFO)
    adapter = TypeAdapter(IngestionEnvelope)
    uploaded = failed = alerts = 0
    for index, raw in enumerate(events, 1):
        envelope = adapter.validate_python(raw)
        result = process(envelope)
        uploaded += result.get("uploaded", 0)
        failed += result.get("failed", 0)
        if result.get("alert"):
            alerts += 1
        if index % 25 == 0:
            print(f"  {index}/{len(events)} events — {uploaded} resources uploaded")
    print(f"\ndone: {uploaded} resources uploaded, {failed} failed, {alerts} alerts raised")


if __name__ == "__main__":
    main()
