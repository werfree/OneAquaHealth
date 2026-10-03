"""Stateful local API and static server for the OneAquaHealth dashboard demo."""

from __future__ import annotations

import copy
import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Query, Response
from fastapi import Path as PathParam
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
load_dotenv(PROJECT_ROOT / ".env")

FIXTURE_PATH = ROOT / "data" / "fixtures.json"
STATIC_ROOT = ROOT / "static"
LIVE_BASE_URL = os.getenv("OAH_LIVE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
# Overview queries and the assistant's multi-round loop need a longer timeout.
LIVE_TIMEOUT_SECONDS = float(os.getenv("OAH_LIVE_TIMEOUT_SECONDS", "90"))
MODES = {"mock", "live"}
DEFAULT_MODE = os.getenv("DASHBOARD_DEFAULT_MODE", "mock").strip().lower()
if DEFAULT_MODE not in MODES:
    DEFAULT_MODE = "mock"
SITE_ID_PATTERN = r"^[A-Za-z0-9.\-]{1,64}$"
THEMES = [
    {"id": "aqua", "label": "Aqua", "themeColor": "#f4f3ee", "colorScheme": "light"},
    {"id": "aqua-dark", "label": "Aqua dark", "themeColor": "#0f1d1a", "colorScheme": "dark"},
    {"id": "white", "label": "White", "themeColor": "#ffffff", "colorScheme": "light"},
    {"id": "dark", "label": "Dark", "themeColor": "#121416", "colorScheme": "dark"},
]
THEME_IDS = {theme["id"] for theme in THEMES}


def resolve_default_theme(value: str | None = None) -> str:
    candidate = (value or os.getenv("DASHBOARD_DEFAULT_THEME", "aqua")).strip().lower()
    return candidate if candidate in THEME_IDS else "aqua"


DEFAULT_THEME = resolve_default_theme()

with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
    FIXTURE = json.load(fixture_file)

app = FastAPI(title="OneAquaHealth dashboard mock", version="1.0.0")
lock = threading.RLock()
runtime: dict[str, Any] = {
    "runSequence": 100,
    "reportSequence": 100,
    "runs": copy.deepcopy(FIXTURE["seedRuns"]),
    "reports": copy.deepcopy(FIXTURE["reports"]),
}

STAGES = [
    ("received", "Received"),
    ("validated", "Validated"),
    ("screened", "Screened"),
    ("mapped", "Mapped"),
    ("bundled", "Bundled"),
    ("upsert", "Upsert outcome"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def persona(role: str | None) -> dict[str, Any]:
    key = (role or "analyst").lower()
    if key not in FIXTURE["personas"]:
        raise HTTPException(status_code=400, detail=f"Unknown demo persona: {key}")
    return {"key": key, **FIXTURE["personas"][key]}


def require(user: dict[str, Any], permission: str) -> None:
    if permission not in user["permissions"]:
        raise HTTPException(status_code=403, detail=f"{user['label']} cannot perform this demo action")


def scoped_site(site_id: str, user: dict[str, Any]) -> dict[str, Any]:
    if site_id not in user["siteIds"]:
        raise HTTPException(status_code=404, detail="Site is outside this persona's scope")
    site = next((item for item in FIXTURE["sites"] if item["id"] == site_id), None)
    if not site:
        raise HTTPException(status_code=404, detail="Unknown site")
    return copy.deepcopy(site)


def sample_for(key: str) -> dict[str, Any]:
    sample = next((item for item in FIXTURE["samples"] if item["key"] == key), None)
    if not sample:
        raise HTTPException(status_code=404, detail="Unknown sample")
    return sample


def stage_payload(stage_id: str, sample: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    raw = sample["raw"]
    site_id = sample["siteId"]
    if stage_id == "received":
        return {
            "summary": "Payload received; no trust decision has been made.",
            "input": raw,
            "counts": {"events": 1},
        }
    if stage_id == "validated":
        return {
            "summary": "Envelope matched the source discriminator and required site/time fields.",
            "output": {
                "eventId": raw["event_id"],
                "sourceType": raw["source_type"],
                "siteId": site_id,
                "effectiveAt": raw["timestamp"],
                "valid": True,
            },
            "counts": {"accepted": 1, "rejected": 0},
        }
    if stage_id == "screened":
        nitrate = sample["key"] == "iot"
        return {
            "summary": "Deterministic prototype rules evaluated before FHIR conversion.",
            "output": {
                "severity": "HIGH" if nitrate else "NONE",
                "exceedances": [
                    {"indicator": "nitrate", "value": 14.2, "unit": "mg/L as NO3-N", "threshold": 11.3, "factor": 1.26},
                    {"indicator": "zinc_dissolved", "value": 0.05, "unit": "mg/L", "threshold": 0.0078},
                ] if nitrate else [],
                "notice": FIXTURE["meta"]["screeningNotice"],
            },
            "counts": {"rulesEvaluated": 3 if nitrate else 0, "findings": 2 if nitrate else 0},
        }
    if stage_id == "mapped":
        mapping = {
            "iot": {"Location": 1, "Device": 1, "Specimen": 1, "Observation": 3},
            "survey": {"Location": 1, "Practitioner": 1, "Specimen": 1, "Observation": 3},
            "health": {"Location": 1, "Group": 1, "Organization": 1, "Observation": 1},
            "health-mondego": {"Location": 1, "Group": 1, "Organization": 1, "Observation": 2},
        }[sample["key"]]
        data = {
            "summary": "Validated domain data mapped to OAH-profiled FHIR R4 resources.",
            "output": {"profiles": ["Location-oah", "Observation-oah"], "resourceCounts": mapping},
            "counts": mapping,
        }
        if sample.get("warning"):
            data["warnings"] = [sample["warning"]]
        return data
    if stage_id == "bundled":
        return {
            "summary": "Resources deduplicated by resourceType/id and prepared as transaction PUTs.",
            "output": {"type": "transaction", "idempotent": True, "entryMethod": "PUT", "datasetTag": FIXTURE["meta"]["datasetTag"]},
            "counts": {"entries": 6 if sample["sourceType"] != "PUBLIC_HEALTH" else 4},
        }
    success = run.get("forceSuccess") or sample["scenario"] != "failure"
    return {
        "summary": "FHIR transaction confirmed by the response." if success else "FHIR transaction could not be completed.",
        "output": {
            "fhir": "UPLOADED" if success else "UPLOAD_FAILED",
            "uploaded": 6 if success else 0,
            "failed": 0 if success else 4,
        },
        "errors": [] if success else ["FHIR transaction service unavailable"],
        "counts": {"uploaded": 6 if success else 0, "failed": 0 if success else 4},
    }


def materialize_run(source: dict[str, Any]) -> dict[str, Any]:
    run = copy.deepcopy(source)
    sample = sample_for(run["sampleKey"])
    dynamic = "startedEpoch" in run
    elapsed = max(0.0, time.time() - run.get("startedEpoch", time.time())) if dynamic else 99.0
    terminal_after = 4.8 if not run.get("retryOf") else 3.2
    success = run.get("forceSuccess") or sample["scenario"] != "failure"
    if dynamic:
        if elapsed >= terminal_after:
            run["executionStatus"] = "completed" if success else "failed"
            run["fhirOutcome"] = "UPLOADED" if success else "UPLOAD_FAILED"
            run["completedAt"] = run.get("completedAt") or utc_now()
            source.update({key: run[key] for key in ("executionStatus", "fhirOutcome", "completedAt")})
        else:
            run["executionStatus"] = "running"
            run["fhirOutcome"] = None

    stages: list[dict[str, Any]] = []
    for index, (stage_id, name) in enumerate(STAGES):
        payload = stage_payload(stage_id, sample, run)
        stage: dict[str, Any] = {"id": stage_id, "name": name, "status": "pending", **payload}
        if not dynamic:
            if run["executionStatus"] == "failed" and stage_id == "upsert":
                stage["status"] = "failed"
            elif run["executionStatus"] == "running" and index == 3:
                stage["status"] = "running"
            elif run["executionStatus"] == "running" and index > 3:
                stage["status"] = "pending"
            else:
                stage["status"] = "warning" if stage_id == "mapped" and sample.get("warning") else "completed"
        else:
            stage_start = index * (terminal_after / len(STAGES))
            stage_end = (index + 1) * (terminal_after / len(STAGES))
            if elapsed >= stage_end:
                if stage_id == "upsert" and not success:
                    stage["status"] = "failed"
                elif stage_id == "mapped" and sample.get("warning"):
                    stage["status"] = "warning"
                else:
                    stage["status"] = "completed"
            elif elapsed >= stage_start:
                stage["status"] = "running"
            else:
                stage["status"] = "pending"
        if stage["status"] == "pending":
            stage = {"id": stage_id, "name": name, "status": "pending", "summary": "Stage has not started."}
        elif stage["status"] == "running":
            stage.pop("output", None)
            stage.pop("counts", None)
            stage.pop("warnings", None)
            stage.pop("errors", None)
        stages.append(stage)
    run["stages"] = stages
    run["sampleLabel"] = sample["label"]
    run["progress"] = round(sum(stage["status"] in {"completed", "warning", "failed"} for stage in stages) / len(stages) * 100)
    run.pop("startedEpoch", None)
    run.pop("forceSuccess", None)
    return run


def report_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    site = next(site for site in FIXTURE["sites"] if site["id"] == report["siteId"])
    observations = [copy.deepcopy(item) for item in FIXTURE["observations"] if item["id"] in report["snapshotObservationIds"]]
    findings = [copy.deepcopy(item) for item in FIXTURE["findings"] if item["id"] in report["snapshotFindingIds"]]
    evidence_ids = {evidence_id for finding in findings for evidence_id in finding.get("evidenceIds", [])}
    evidence = [copy.deepcopy(item) for item in FIXTURE["evidence"] if item["id"] in evidence_ids]
    return {
        "id": report["id"],
        "title": report["title"],
        "site": {key: site[key] for key in ("id", "name", "city")},
        "timeScope": {"latestEnvironmentalSample": "2026-09-30T10:00:00Z", "healthEvaluationPeriod": "2026-01-01 to 2026-09-27"},
        "generatedAt": report.get("generatedAt"),
        "observations": observations,
        "findings": findings,
        "evidence": evidence,
        "limitations": [
            "Association only, not causation.",
            "Environmental samples and the health evaluation period are not contemporaneous.",
            FIXTURE["meta"]["screeningNotice"],
            FIXTURE["meta"]["coordinateNotice"],
        ],
    }


def report_html(report: dict[str, Any]) -> str:
    snapshot = report_snapshot(report)
    observations = "".join(
        f"<tr><td>{html.escape(item['indicator'])}</td><td>{html.escape(str(item.get('value', item.get('codedValue', '—'))))} {html.escape(item.get('unit', ''))}</td><td>{html.escape(item['interpretation'])}</td></tr>"
        for item in snapshot["observations"]
    )
    findings = "".join(f"<li><strong>{html.escape(item['title'])}</strong><br>{html.escape(item['statement'])}</li>" for item in snapshot["findings"])
    limitations = "".join(f"<li>{html.escape(item)}</li>" for item in snapshot["limitations"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(snapshot['title'])}</title><style>
body{{font:15px/1.55 Arial,sans-serif;color:#17231f;max-width:900px;margin:40px auto;padding:0 28px}} h1{{font-size:28px}} h2{{margin-top:30px;font-size:18px}} .meta{{color:#56645f}} table{{width:100%;border-collapse:collapse}} th,td{{padding:10px;border-bottom:1px solid #d9dfdc;text-align:left;vertical-align:top}} .notice{{border-left:4px solid #b97822;background:#fff8ea;padding:12px 16px}} @media print{{body{{margin:0;max-width:none}} .print-note{{display:none}}}}
</style></head><body><p class="meta">OneAquaHealth · Site One Health Briefing</p><h1>{html.escape(snapshot['site']['name'])}</h1>
<p class="meta">Generated {html.escape(snapshot['generatedAt'] or 'pending')} · Health period {html.escape(snapshot['timeScope']['healthEvaluationPeriod'])}</p>
<p class="notice"><strong>Interpret carefully.</strong> Association only, not causation. The environmental sample and health evaluation period are not contemporaneous.</p>
<h2>Source observations</h2><table><thead><tr><th>Measure</th><th>Value</th><th>Interpretation</th></tr></thead><tbody>{observations}</tbody></table>
<h2>Findings</h2><ul>{findings}</ul><h2>Limitations</h2><ul>{limitations}</ul><p class="print-note">Use your browser's Print / Save as PDF command for a PDF copy.</p></body></html>"""


def materialize_report(source: dict[str, Any]) -> dict[str, Any]:
    report = copy.deepcopy(source)
    if "requestedEpoch" in report and report["status"] != "generated":
        if time.time() - report["requestedEpoch"] >= 3:
            source["status"] = report["status"] = "generated"
            source["generatedAt"] = report["generatedAt"] = utc_now()
        elif time.time() - report["requestedEpoch"] >= 0.5:
            report["status"] = "generating"
    report.pop("requestedEpoch", None)
    if report["status"] == "generated":
        snapshot = report_snapshot(report)
        json_bytes = json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8")
        html_bytes = report_html(report).encode("utf-8")
        report["files"] = [
            {"format": "html", "mimeType": "text/html", "sizeBytes": len(html_bytes)},
            {"format": "json", "mimeType": "application/json", "sizeBytes": len(json_bytes)},
        ]
        report["snapshot"] = snapshot
    return report


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "oneaquahealth-dashboard-mock"}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {"defaultTheme": DEFAULT_THEME, "themes": THEMES, "defaultMode": DEFAULT_MODE}


@app.get("/api/mock/session")
def get_session(x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    permissions = set(user["permissions"])
    return {
        "persona": user,
        "capabilities": {
            "canQueryAssistant": "assistant.ask" in permissions,
            "canTrackRuns": "ingestion.read" in permissions,
            "canStartRuns": "ingestion.create" in permissions,
            "canRetryRuns": "ingestion.retry" in permissions,
            "canGenerateReports": "report.create" in permissions,
            "canLoadGraph": "graph.read" in permissions,
            "canReadEvidence": "evidence.read" in permissions,
            "hasServerAuthorization": True,
        },
        "mode": "mock",
        "notices": [
            "Demo personas simulate a proposed policy; they are not current production authentication.",
            FIXTURE["meta"]["screeningNotice"],
        ],
    }


@app.get("/api/mock/summary")
def get_summary(x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "dashboard.read")
    sites = [copy.deepcopy(item) for item in FIXTURE["sites"] if item["id"] in user["siteIds"]]
    site_ids = {item["id"] for item in sites}
    observations = [item for item in FIXTURE["observations"] if item["siteId"] in site_ids]
    findings = [item for item in FIXTURE["findings"] if item["siteId"] in site_ids]
    for site in sites:
        site["observationCount"] = sum(item["siteId"] == site["id"] for item in observations)
        site["findingCount"] = sum(item["siteId"] == site["id"] for item in findings)
        site.pop("observationIds", None)
        site.pop("findingIds", None)
    return {
        "metrics": {
            "sitesInScope": len(sites),
            "loadedObservations": len(observations),
            "screeningFindings": sum(item["type"] == "threshold" for item in findings),
            "coLocatedSites": len({item["siteId"] for item in findings if item["type"] == "co-location"}),
        },
        "sites": sites,
        "scopeLabel": f"{len(sites)} site{'s' if len(sites) != 1 else ''} in demo scope",
        "countNotice": "Counts describe loaded mock records, not global totals.",
    }


@app.get("/api/mock/sites/{site_id}")
def get_site(site_id: str, x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "dashboard.read")
    site = scoped_site(site_id, user)
    observations = [copy.deepcopy(item) for item in FIXTURE["observations"] if item["siteId"] == site_id]
    findings = [copy.deepcopy(item) for item in FIXTURE["findings"] if item["siteId"] == site_id]
    if "evidence.read" not in user["permissions"]:
        for finding in findings:
            finding.pop("evidenceIds", None)
    site.pop("observationIds", None)
    site.pop("findingIds", None)
    return {"site": site, "observations": observations, "findings": findings, "meta": FIXTURE["meta"]}


@app.get("/api/mock/evidence/{evidence_id}")
def get_evidence(evidence_id: str, x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "evidence.read")
    evidence = next((copy.deepcopy(item) for item in FIXTURE["evidence"] if item["id"] == evidence_id), None)
    if not evidence or evidence["siteId"] not in user["siteIds"]:
        raise HTTPException(status_code=404, detail="Evidence is outside this persona's scope")
    return evidence


@app.get("/api/mock/graph")
def get_graph(site_id: str = Query(alias="siteId"), x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "graph.read")
    scoped_site(site_id, user)
    nodes = [copy.deepcopy(item) for item in FIXTURE["graph"]["nodes"] if item["siteId"] == site_id]
    node_ids = {item["id"] for item in nodes}
    edges = [copy.deepcopy(item) for item in FIXTURE["graph"]["edges"] if item["siteId"] == site_id and item["source"] in node_ids and item["target"] in node_ids]
    return {"siteId": site_id, "nodes": nodes[:10], "edges": edges, "complete": True, "source": "Locally assembled from supplied FHIR references and derived findings"}


@app.post("/api/mock/assistant")
def ask_assistant(payload: dict[str, Any] = Body(...), x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "assistant.ask")
    site_id = str(payload.get("siteId", ""))
    scoped_site(site_id, user)
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question is required")
    normalized = question.lower()
    if "contempor" in normalized or "same time" in normalized:
        answer = "No. The environmental sample is dated 30 September 2026, while the health score summarizes 1 January–27 September 2026. Their shared Location supports co-location, not temporal alignment."
        refs = ["Observation/nitrate-site-c1-mondego-1759226400-1", "Observation/overall-health-risk-site-c1-mondego-1759190400-r3"]
    elif "evidence" in normalized or "co-location" in normalized or "colocation" in normalized:
        answer = "The finding is supported by the nitrate Observation, the agency-classified health-risk Observation, and the riverside Group, all linked to Mondego C1. Association only, not causation."
        refs = ["evidence-nitrate-observation", "evidence-health-observation", "evidence-health-cohort"]
    elif "attention" in normalized or "nitrate" in normalized or "zinc" in normalized:
        answer = "Mondego C1 has two prototype screening flags: nitrate at 14.2 mg/L as NO3-N and dissolved zinc at 0.05 mg/L. A separate cohort aggregate is classified HIGH by the reporting agency."
        refs = ["evidence-nitrate-observation", "evidence-zinc-observation", "evidence-health-observation"]
    else:
        answer = "This deterministic demo only supports questions about Mondego C1 findings, their evidence, and whether the source periods align. Try one of the suggested questions."
        refs = []
    return {
        "question": question,
        "answer": answer,
        "trace": [
            {"kind": "TOOL", "label": "Load scoped site profile", "status": "completed", "input": {"siteId": site_id}},
            {"kind": "FHIR_QUERY", "label": "Resolve referenced records", "status": "completed", "evidenceRefs": refs},
            {"kind": "GROUNDING", "label": "Check numeric literals against returned evidence", "status": "completed", "grounded": bool(refs)},
        ],
        "grounding": {"grounded": bool(refs), "unsupportedFigures": [], "notCovered": "Numeric matching does not verify the full answer."},
        "model": "deterministic-mock",
    }


@app.get("/api/mock/runs")
def list_runs(x_demo_role: str | None = Header(default="operator")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "ingestion.read")
    with lock:
        runs = [materialize_run(item) for item in runtime["runs"] if item["siteId"] in user["siteIds"]]
    runs.sort(key=lambda item: item["startedAt"], reverse=True)
    samples = [{key: item[key] for key in ("key", "label", "description", "siteId", "sourceType", "scenario")} for item in FIXTURE["samples"] if item["siteId"] in user["siteIds"]]
    return {"runs": runs, "samples": samples, "stateNotice": "Runtime state persists across browser refresh and resets when this mock server restarts."}


@app.post("/api/mock/runs", status_code=202)
def start_run(payload: dict[str, Any] = Body(...), x_demo_role: str | None = Header(default="operator")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "ingestion.create")
    sample = sample_for(str(payload.get("sampleKey", "")))
    scoped_site(sample["siteId"], user)
    with lock:
        if any(item.get("startedEpoch") and materialize_run(item)["executionStatus"] == "running" and item["sampleKey"] == sample["key"] for item in runtime["runs"]):
            raise HTTPException(status_code=409, detail="This sample already has an active run")
        runtime["runSequence"] += 1
        run = {
            "id": f"run-{runtime['runSequence']}",
            "sampleKey": sample["key"],
            "siteId": sample["siteId"],
            "sourceType": sample["sourceType"],
            "executionStatus": "running",
            "fhirOutcome": None,
            "startedAt": utc_now(),
            "startedEpoch": time.time(),
            "attempt": 1,
        }
        runtime["runs"].append(run)
        return materialize_run(run)


@app.get("/api/mock/runs/{run_id}")
def get_run(run_id: str, x_demo_role: str | None = Header(default="operator")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "ingestion.read")
    with lock:
        run = next((item for item in runtime["runs"] if item["id"] == run_id and item["siteId"] in user["siteIds"]), None)
        if not run:
            raise HTTPException(status_code=404, detail="Run is outside this persona's scope")
        return materialize_run(run)


@app.post("/api/mock/runs/{run_id}/retry", status_code=202)
def retry_run(run_id: str, x_demo_role: str | None = Header(default="operator")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "ingestion.retry")
    with lock:
        original = next((item for item in runtime["runs"] if item["id"] == run_id and item["siteId"] in user["siteIds"]), None)
        if not original:
            raise HTTPException(status_code=404, detail="Run is outside this persona's scope")
        current = materialize_run(original)
        if current["executionStatus"] != "failed":
            raise HTTPException(status_code=409, detail="Only failed runs can be retried")
        runtime["runSequence"] += 1
        run = {
            "id": f"run-{runtime['runSequence']}",
            "sampleKey": original["sampleKey"],
            "siteId": original["siteId"],
            "sourceType": original["sourceType"],
            "executionStatus": "running",
            "fhirOutcome": None,
            "startedAt": utc_now(),
            "startedEpoch": time.time(),
            "attempt": int(original.get("attempt", 1)) + 1,
            "retryOf": original["id"],
            "forceSuccess": True,
        }
        runtime["runs"].append(run)
        return materialize_run(run)


@app.post("/api/mock/reset")
def reset_demo(x_demo_role: str | None = Header(default="operator")) -> dict[str, str]:
    user = persona(x_demo_role)
    require(user, "ingestion.create")
    with lock:
        runtime["runs"] = copy.deepcopy(FIXTURE["seedRuns"])
        runtime["reports"] = copy.deepcopy(FIXTURE["reports"])
    return {"status": "reset"}


def accessible_reports(user: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for source in runtime["reports"]:
        if source["siteId"] not in user["siteIds"]:
            continue
        if user["key"] == "viewer" and source["visibility"] != "published":
            continue
        if user["key"] == "operator":
            continue
        results.append(materialize_report(source))
    return results


@app.get("/api/mock/reports")
def list_reports(x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    if user["key"] == "operator":
        raise HTTPException(status_code=403, detail="Data operator does not have report access")
    with lock:
        reports = accessible_reports(user)
    return {"reports": reports, "lifecycle": ["requested", "generating", "generated", "failed"]}


@app.post("/api/mock/reports", status_code=202)
def create_report(payload: dict[str, Any] = Body(...), x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    require(user, "report.create")
    site_id = str(payload.get("siteId", ""))
    site = scoped_site(site_id, user)
    observation_ids = [item["id"] for item in FIXTURE["observations"] if item["siteId"] == site_id]
    finding_ids = [item["id"] for item in FIXTURE["findings"] if item["siteId"] == site_id]
    with lock:
        runtime["reportSequence"] += 1
        report = {
            "id": f"report-{runtime['reportSequence']}",
            "siteId": site_id,
            "title": f"{site['shortName']} · Site One Health Briefing",
            "status": "requested",
            "visibility": "draft",
            "ownerId": user["id"],
            "requestedAt": utc_now(),
            "requestedEpoch": time.time(),
            "generatedAt": None,
            "snapshotObservationIds": observation_ids,
            "snapshotFindingIds": finding_ids,
        }
        runtime["reports"].append(report)
        return materialize_report(report)


def get_accessible_report(report_id: str, user: dict[str, Any]) -> dict[str, Any]:
    report = next((item for item in runtime["reports"] if item["id"] == report_id), None)
    if not report or report["siteId"] not in user["siteIds"]:
        raise HTTPException(status_code=404, detail="Report is outside this persona's scope")
    if user["key"] == "operator" or (user["key"] == "viewer" and report["visibility"] != "published"):
        raise HTTPException(status_code=404, detail="Report is outside this persona's scope")
    return materialize_report(report)


@app.get("/api/mock/reports/{report_id}")
def get_report(report_id: str, x_demo_role: str | None = Header(default="analyst")) -> dict[str, Any]:
    user = persona(x_demo_role)
    with lock:
        return get_accessible_report(report_id, user)


@app.get("/api/mock/reports/{report_id}/download/{format_name}")
def download_report(report_id: str, format_name: str, x_demo_role: str | None = Header(default="analyst")) -> Response:
    user = persona(x_demo_role)
    if user["key"] == "viewer":
        require(user, "report.download.published")
    else:
        require(user, "report.download")
    with lock:
        report = get_accessible_report(report_id, user)
    if report["status"] != "generated":
        raise HTTPException(status_code=409, detail="Report is not ready")
    slug = report["siteId"].replace("site-", "")
    if format_name == "html":
        content = report_html(report).encode("utf-8")
        media_type = "text/html"
    elif format_name == "json":
        content = json.dumps(report_snapshot(report), indent=2, ensure_ascii=False).encode("utf-8")
        media_type = "application/json"
    else:
        raise HTTPException(status_code=404, detail="Available formats are html and json")
    return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{slug}-one-health-briefing.{format_name}"'})


def proxy_live(path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> JSONResponse:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(f"{LIVE_BASE_URL}{path}", data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=LIVE_TIMEOUT_SECONDS) as result:
            return JSONResponse(json.loads(result.read().decode("utf-8")), status_code=result.status)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            detail = {"detail": str(exc)}
        return JSONResponse(detail, status_code=exc.code)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=f"Live OneAquaHealth service unavailable: {exc.reason if hasattr(exc, 'reason') else exc}")


@app.get("/api/live/health")
def live_health() -> JSONResponse:
    return proxy_live("/health")


@app.get("/api/live/info")
def live_info() -> JSONResponse:
    return proxy_live("/api/info")


@app.get("/api/live/overview")
def live_overview(refresh: bool = False) -> JSONResponse:
    return proxy_live("/api/overview?refresh=true" if refresh else "/api/overview")


@app.get("/api/live/sites/{site_id}")
def live_site(site_id: str = PathParam(pattern=SITE_ID_PATTERN)) -> JSONResponse:
    return proxy_live(f"/api/sites/{site_id}")


@app.post("/api/live/ingest-demo/{key}")
def live_ingest_demo(key: str) -> JSONResponse:
    if key not in {"iot", "iot-oslo", "iot-benevento", "iot-coimbra", "survey", "survey-ghent", "survey-toulouse", "survey-coimbra", "health", "health-coimbra", "health-mondego", "health-kanpur"}:
        raise HTTPException(status_code=404, detail="Unknown live sample")
    return proxy_live(f"/api/ingest-demo/{key}", method="POST")


@app.post("/api/live/ask")
def live_ask(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    forwarded: dict[str, Any] = {"question": str(payload.get("question", ""))}
    site_id = payload.get("siteId")
    if isinstance(site_id, str) and re.fullmatch(SITE_ID_PATTERN, site_id):
        forwarded["site_id"] = site_id
    return proxy_live("/api/ask", method="POST", payload=forwarded)


@app.get("/", include_in_schema=False)
def index() -> HTMLResponse:
    page = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(page.replace("__DEFAULT_THEME__", DEFAULT_THEME).replace("__DEFAULT_MODE__", DEFAULT_MODE))


def studio_upstream(path: str, payload: dict[str, Any] | None = None):
    """Open only the fixed Studio routes selected by the handlers below."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{LIVE_BASE_URL}/api/officer/{path}", data=body,
        headers={"Content-Type": "application/json", "Accept": "*/*"},
    )
    try:
        return urllib.request.urlopen(request, timeout=LIVE_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail", str(exc))
        except (ValueError, UnicodeDecodeError):
            detail = str(exc)
        finally:
            exc.close()
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail="Surveillance service unavailable. Start the ingestion gateway and try again.") from exc


@app.post("/api/live/studio/run")
def live_studio_run(payload: dict[str, Any] = Body(...)) -> StreamingResponse:
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise HTTPException(status_code=422, detail="Enter a question of 1–4000 characters.")
    site_id = payload.get("siteId")
    if site_id is not None and (not isinstance(site_id, str) or not re.fullmatch(SITE_ID_PATTERN, site_id)):
        raise HTTPException(status_code=422, detail="Invalid station ID")
    scoped_question = question.strip()
    if site_id:
        scoped_question += f"\n\nDashboard context: investigate station {site_id}. Use other stations only where needed for comparison."
    upstream = studio_upstream("studio/run", {"question": scoped_question})
    if not upstream.headers.get("Content-Type", "").startswith("text/event-stream"):
        upstream.close()
        raise HTTPException(status_code=502, detail="Surveillance service returned an invalid stream.")

    def chunks():
        try:
            # read1 returns available bytes without waiting to fill a buffer.
            while chunk := upstream.read1(4096):
                yield chunk
        except (OSError, TimeoutError):
            yield b'data: {"type":"error","message":"The investigation connection was interrupted. Please retry."}\n\n'
        finally:
            upstream.close()

    return StreamingResponse(chunks(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                             background=BackgroundTask(upstream.close))


def studio_document(path: str, payload: dict[str, Any] | None = None) -> Response:
    with studio_upstream(path, payload) as upstream:
        headers = {}
        if disposition := upstream.headers.get("Content-Disposition"):
            headers["Content-Disposition"] = disposition
        headers["Content-Type"] = upstream.headers.get("Content-Type", "application/octet-stream")
        return Response(upstream.read(), status_code=upstream.status, headers=headers)


@app.get("/api/live/studio/transcript/{session_id}")
def live_studio_transcript(session_id: str = PathParam(pattern=r"^[A-Za-z0-9-]{1,64}$")) -> Response:
    return studio_document(f"studio/report/{session_id}")


@app.post("/api/live/studio/executive")
def live_studio_executive(payload: dict[str, Any] = Body(...)) -> Response:
    session_id = payload.get("session")
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", session_id):
        raise HTTPException(status_code=422, detail="Invalid investigation session")
    figures = payload.get("figures", [])
    if not isinstance(figures, list) or len(figures) > 30 or any(not isinstance(figure, dict) for figure in figures):
        raise HTTPException(status_code=422, detail="Invalid report figures")
    return studio_document("studio/executive", {"session": session_id, "figures": figures})


@app.get("/api/live/studio/export/{kind}")
def live_studio_export(kind: str, days: int = Query(28, ge=1, le=365),
                      site_id: str | None = Query(None, pattern=SITE_ID_PATTERN)) -> Response:
    exports = {"readings": "readings.csv", "surveillance": "surveillance.csv", "fhir": "bundle.json"}
    if kind not in exports:
        raise HTTPException(status_code=404, detail="Unknown Studio export")
    if kind == "fhir" and not site_id:
        raise HTTPException(status_code=422, detail="Choose a station for the FHIR export")
    params: dict[str, Any] = {"days": days}
    if site_id and kind != "surveillance":
        params["site_id"] = site_id
    return studio_document(f"export/{exports[kind]}?{urllib.parse.urlencode(params)}")


@app.get("/studio", include_in_schema=False)
def studio() -> HTMLResponse:
    """Serve the native dashboard workspace with live Studio selected."""
    return index()


app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run("dashboard.server:app", host="127.0.0.1", port=int(os.getenv("DASHBOARD_PORT", "8090")), reload=False)


if __name__ == "__main__":
    main()
