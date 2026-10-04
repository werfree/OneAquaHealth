#!/usr/bin/env python
"""Capture the live evidence values used by the video panels (read-only).

Writes JSON + a text alert into video/_build/data/. No writes to the FHIR server.
"""
from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

OUT = Path("video/_build/data")
OUT.mkdir(parents=True, exist_ok=True)
GW = os.getenv("OAH_GATEWAY", "http://127.0.0.1:8000")


def get(path: str):
    with urllib.request.urlopen(GW + path, timeout=120) as r:
        return json.load(r)


def save(name: str, obj) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=1), encoding="utf-8")
    print("saved", name)


save("info", get("/api/info"))
save("trend", get("/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28"))
save("profile", get("/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28"))
save("persistence", get("/api/officer/persistence?days=28"))
save("offset", get("/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28"))
save("wards", get("/api/officer/wards?days=28"))
save("facts", get("/api/officer/report/facts?days=28"))

# Real pipeline run with upload disabled (no write) -> alert text + resource counts.
os.environ["FHIR_UPLOAD_ENABLED"] = "false"
import sys

sys.path[:0] = [
    "oah-ingestion/src",
    "oah-pydantic-models/src",
    "oah-agent/src",
]
from pydantic import TypeAdapter  # noqa: E402

from oah_ingestion.alerts import assess, format_alert  # noqa: E402
from oah_ingestion.envelope import IngestionEnvelope, envelope_as_message  # noqa: E402
from oah_ingestion.fhir_adapter import envelope_to_fhir  # noqa: E402
from oah_ingestion.pipeline import process  # noqa: E402

raw = json.loads(Path("demo/sample_iot_telemetry.json").read_text(encoding="utf-8"))
env = TypeAdapter(IngestionEnvelope).validate_python(raw)
alert_text = format_alert(assess(env))
resources = dict(Counter(r.resourceType for r in envelope_to_fhir(env)))
result = process(env, envelope_as_message(env))
payload = {
    "alert_text": alert_text,
    "resource_counts": resources,
    "client_side_counts": resources,
    "pipeline_fhir": result.get("fhir"),
    "upload": {k: v for k, v in result.items() if k != "alert"},
}
(OUT / "ingest.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
print("saved ingest;", "fhir:", result.get("fhir"), "counts:", resources)
print(alert_text)
