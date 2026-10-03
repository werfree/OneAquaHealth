# Handoff prompt: connect the OneAquaHealth evidence dashboard to live FHIR data
> Copy everything below the line into the other LLM. It is self-contained.
---
You are working on the **OneAquaHealth** repository, a Python/FastAPI hackathon prototype (IEEE Global Hackathon 2026, Track 7). Your task is to make the **evidence dashboard** show data that is **already stored on the public HAPI FHIR sandbox** (`https://hapi.fhir.org/baseR4`), read through the ingestion gateway. **No ingestion is required**; the data was uploaded earlier.
Apply the changes below exactly, then run the tests and the verification steps. If a change below already exists in the code, confirm it matches and move on. Do not redesign; keep the existing code style (docstrings that explain *why*, stdlib `urllib` for HTTP, no new dependencies).
## 1. Project background (read first)
Repository layout:
| Path | Role |
|---|---|
| `oah-pydantic-models/` | OAH logical models and OAH → FHIR R4 mappers (`oah_models.fhir`) |
| `oah-ingestion/` | **Gateway** FastAPI app (`python -m oah_ingestion.app`, port from `APP_PORT`). Starts an MQTT listener, a RabbitMQ consumer thread, `POST /ingest`, and the read API in `web.py` |
| `oah-agent/` | FHIR query tools (`tools.py`), cross-domain briefing (`briefing.py`), OpenAI assistant (`assistant.py`), grounding check |
| `oah-demo-publishers/` | Sends demo samples over MQTT/RabbitMQ/HTTP |
| `dashboard/` | **Separate** evidence dashboard: FastAPI `server.py` (port 8090, command `oah-dashboard`) + vanilla JS in `static/js/` (`api.js`, `app.js`, `state.js`, `components.js`) |
Dependency direction: `oah-agent` → `oah-ingestion` → `oah-pydantic-models`. The gateway imports `oah_agent` **lazily inside route functions** (to avoid a circular import); keep it that way.
Data flow for the dashboard in live mode:
```
Browser :8090 --/api/live/*--> dashboard/server.py (allow-listed proxy, proxy_live())
   --> gateway :8001 (/api/overview, /api/sites/{id}, /api/ask)
   --> oah_agent tools --> HAPI FHIR searches, always scoped with
       _tag=http://hl7.eu/fhir/ig/oah/CodeSystem/dataset-tag|<OAH_DATASET_TAG, default oah-demo>
```
The dashboard has two adapters in `dashboard/static/js/api.js`: `mockAdapter` (fixtures in `dashboard/data/fixtures.json`) and `liveAdapter`. Live mode was selected only by `?mode=live`.
The data on HAPI: `GET https://hapi.fhir.org/baseR4/Observation?_tag=http://hl7.eu/fhir/ig/oah/CodeSystem/dataset-tag|oah-demo&_summary=count` returned **total 918**, and the gateway's overview found **9 sites** (including `site-c1-mondego`, `site-coimbra-t1`, `yam-okhla`, `mit-dharavi`).
### Problems that blocked live mode (what you are fixing)
1. `oah_ingestion/fhir_client.py` `search()` read **only the first page** of a FHIR searchset and ignored `link[relation=next]`. With 918 Observations and `_count` ≤ 200, sites were silently truncated.
2. `dashboard/server.py` `proxy_live()` used a hard-coded **8 s timeout**. `/api/overview` makes ~3–4 sequential HAPI calls per site, and `/api/ask` runs a multi-round OpenAI tool loop, so both returned **502 "Live OneAquaHealth service unavailable"**.
3. `liveAdapter.site()` read `source.environmental_readings` / `source.health_measures`, which **the gateway never returns** (`site_briefing()` returned only counts, `exceedances`, `risks`, `elevated_risks`, `cohorts`). Station pages showed **zero observations**.
4. `liveAdapter.summary()` used `data.sites_with_exceedances` and `data.sites_with_co_location` as counts, but they are **lists of site ids**, so metric tiles rendered text like `site-c1-mondego`.
5. `normalizeLiveSite()` expected `city` and `observed_at`, which the overview never set (UI showed "Pilot dataset" / "No observation time").
6. Elevated health risks were never shown as findings.
7. `/api/ask` had no station context (`liveAdapter.ask` dropped `siteId`).
8. The overview was recomputed on every request (slow) and dataset briefings ran sites sequentially.
9. The gateway always started MQTT + RabbitMQ workers; when RabbitMQ is unreachable it floods the log (harmless for reads, but noisy).
## 2. Changes to make
### 2.1 `oah-ingestion/src/oah_ingestion/fhir_client.py`: follow pagination
Replace the existing `search()` with the following (keep `search_url()` and the rest unchanged). `os`, `urllib.parse`, `Optional`, `Dict`, `List` are already imported in this file.
```python
def max_search_results() -> int:
    """Upper bound on resources one `search()` collects across all pages."""
return int(os.getenv("FHIR_MAX_SEARCH_RESULTS", "5000"))
def _next_link(bundle: dict) -> Optional[str]:
for link in bundle.get("link", []):
if link.get("relation") == "next" and link.get("url"):
return link["url"]
return None
def search(
    resource_type: str, params: Dict[str, str], *, timeout: int = 60, max_results: Optional[int] = None
) -> List[dict]:
    """Run a FHIR search and return the matching resources from every page.
    `params` are FHIR search parameters, e.g.
    `{"_profile": OBSERVATION_WITH_COMPONENT_PROFILE, "code": "nitrate"}`.
    A searchset Bundle holds one page; the rest sit behind `link[relation=next]`.
    Reading only the first page silently truncated any site with more readings
    than `_count`, so this follows `next` until the server stops offering one or
    `max_results` (default `FHIR_MAX_SEARCH_RESULTS`) is reached.
    """
    limit = max_search_results() if max_results is None else max_results
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url: Optional[str] = f"{base_url()}/{resource_type}?{query}"
    resources: List[dict] = []
    seen_urls = set()
while url and url not in seen_urls and len(resources) < limit:
        seen_urls.add(url)
        logger.debug("FHIR GET %s", url)
        bundle = _request("GET", url, timeout=timeout)
        resources.extend(entry["resource"] for entry in bundle.get("entry", []) if "resource" in entry)
        url = _next_link(bundle)
if url and len(resources) >= limit:
        logger.warning("FHIR search for %s stopped at %d resources (FHIR_MAX_SEARCH_RESULTS)", resource_type, limit)
return resources[:limit]
```
`seen_urls` guards against a server returning a `next` link that points back to an already-fetched page.
### 2.2 `oah-agent/src/oah_agent/briefing.py`: richer site briefings, parallel dataset briefing
1. Imports at the top become:
   ```python
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from oah_ingestion.sites import lookup
from .tools import get_cohort, get_site_profile, list_sites
   ```
2. Add above `site_briefing`:
   ```python
   def _latest(observations: List[dict]) -> Optional[str]:
       """Most recent effective time; ISO-8601 strings in one offset sort lexically."""
       times = [o["when"] for o in observations if o.get("when")]
return max(times) if times else None
   ```
3. Change `site_briefing` signature to
   `def site_briefing(site_id: str, dataset_tag: str = "oah-demo", *, include_observations: bool = False) -> dict:`
   with a docstring explaining that `include_observations` adds the summarized Observations for a station view and is **off by default so the dataset-wide briefing (which `narrate()` sends to the LLM) stays small**.
4. Inside `site_briefing`, after computing `cohorts`, add `site = lookup(site_id)`, build the dict into a variable `briefing`, and add two keys right after `"site_id"`:
   ```python
   "city": site.city,
   "observed_at": _latest(environmental + health),
   ```
   Keep every existing key (`environmental_reading_count`, `health_measure_count`, `exceedances`, `risks`, `elevated_risks`, `cohorts`, `co_location`, `fhir_urls`, `caveat`). At the end:
   ```python
if include_observations:
       briefing["environmental_observations"] = environmental
       briefing["health_observations"] = health
return briefing
   ```
5. Replace `dataset_briefing` body so sites are briefed concurrently and carry the FHIR Location's own name/position:
   ```python
   def dataset_briefing(dataset_tag: str = "oah-demo") -> dict:
       """Run `site_briefing` across every site in the dataset.
       Each site costs several FHIR round trips, so sites are briefed concurrently
       (`OAH_BRIEFING_WORKERS`, default 8) rather than one after another.
       """
       sites = list_sites(dataset_tag=dataset_tag).get("sites", [])
       workers = max(1, int(os.getenv("OAH_BRIEFING_WORKERS", "8")))
with ThreadPoolExecutor(max_workers=workers) as pool:
           briefings = list(pool.map(lambda site: site_briefing(site["site_id"], dataset_tag=dataset_tag), sites))
       # The FHIR Location's own name/position, so sites missing from the local
       # gazetteer can still be labelled and mapped.
for briefing, site in zip(briefings, sites):
           briefing["name"] = site.get("name")
           briefing["latitude"] = site.get("latitude")
           briefing["longitude"] = site.get("longitude")
return {
           "site_count": len(briefings),
           "sites_with_exceedances": [b["site_id"] for b in briefings if b["exceedances"]],
           "sites_with_elevated_risk": [b["site_id"] for b in briefings if b["elevated_risks"]],
           "sites_with_co_location": [b["site_id"] for b in briefings if b["co_location"]],
           "briefings": briefings,
       }
   ```
### 2.3 `oah-ingestion/src/oah_ingestion/web.py`: cached overview, new site route, ask context
1. Imports: add `os`, `threading`, `time`, `from datetime import datetime, timezone`, and `from fastapi import Path as PathParam` (a plain `Path` would clash with `pathlib.Path`, which this file already uses). Remove the now-redundant local `import os` inside `info()`.
2. In `ingest_demo`, right after `result = process(envelope, envelope_as_message(envelope))`, add:
   ```python
if result.get("fhir") == "UPLOADED":
       invalidate_overview()
   ```
3. Replace the old `overview()` (which looped over `registry()` to set name/lat/lon) with:
   ```python
   def _with_site_details(briefing: dict) -> dict:
       """Fill name/position/city: the FHIR Location first, the gazetteer as fallback."""
       site = registry().get(briefing["site_id"])
if site is not None:
           briefing["name"] = briefing.get("name") or site.name
if briefing.get("latitude") is None or briefing.get("longitude") is None:
               briefing["latitude"], briefing["longitude"] = site.latitude, site.longitude
           briefing["city"] = briefing.get("city") or site.city
       briefing["name"] = briefing.get("name") or briefing["site_id"]
return briefing
   # Every overview costs several FHIR round trips per site; a short-lived cache
   # keeps page loads and the dashboard's repeated reads from re-running them all.
   _overview_cache: dict = {"at": 0.0, "tag": None, "facts": None}
   _overview_lock = threading.Lock()
   def _overview_cache_seconds() -> float:
return float(os.getenv("OVERVIEW_CACHE_SECONDS", "60"))
   def invalidate_overview() -> None:
with _overview_lock:
           _overview_cache["facts"] = None
   @router.get("/api/overview")
   def overview(refresh: bool = False):
       """Current state of the dataset on the FHIR server, with the cross-domain join.
       Cached for `OVERVIEW_CACHE_SECONDS` (default 60); `?refresh=true` bypasses it.
       """
try:
from oah_agent.briefing import dataset_briefing
except ImportError:
raise HTTPException(status_code=501, detail="oah-agent is not installed; overview needs its query tools")
       tag = dataset_tag()
with _overview_lock:
           cached = _overview_cache["facts"]
           fresh = time.monotonic() - _overview_cache["at"] < _overview_cache_seconds()
if cached is not None and fresh and _overview_cache["tag"] == tag and not refresh:
return cached
       facts = dataset_briefing(dataset_tag=tag)
for briefing in facts["briefings"]:
           _with_site_details(briefing)
       facts["fhir_server"] = base_url()
       facts["dataset_tag"] = tag
       facts["generated_at"] = datetime.now(timezone.utc).isoformat()
with _overview_lock:
           _overview_cache.update(at=time.monotonic(), tag=tag, facts=facts)
return facts
   @router.get("/api/sites/{site_id}")
   def site_detail(site_id: str = PathParam(pattern=r"^[A-Za-z0-9.\-]{1,64}$")):
       """One site's briefing including its summarized Observations, for a station view."""
try:
from oah_agent.briefing import site_briefing
from oah_agent.tools import list_sites
except ImportError:
raise HTTPException(status_code=501, detail="oah-agent is not installed; site detail needs its query tools")
       briefing = site_briefing(site_id, dataset_tag=dataset_tag(), include_observations=True)
if not briefing["environmental_reading_count"] and not briefing["health_measure_count"]:
raise HTTPException(status_code=404, detail=f"No observations for site {site_id!r} in dataset {dataset_tag()!r}")
       location = next((s for s in list_sites(dataset_tag=dataset_tag()).get("sites", []) if s["site_id"] == site_id), {})
       briefing.update({k: location.get(k) for k in ("name", "latitude", "longitude")})
       briefing = _with_site_details(briefing)
       briefing["fhir_server"] = base_url()
       briefing["dataset_tag"] = dataset_tag()
return briefing
   ```
4. Extend `Question` and `ask`:
   ```python
   class Question(BaseModel):
       question: str = Field(min_length=1, max_length=500)
       site_id: Optional[str] = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9.\-]+$")
   ```
   In `ask()`, before calling the assistant:
   ```python
   question = body.question
if body.site_id:
       question = f"[Context: the user is viewing site_id {body.site_id}.]\n{question}"
   ```
   and call `run(question)` instead of `run(body.question)`. Keep returning `"question": body.question` (the user's original text) in the response.
### 2.4 `oah-ingestion/src/oah_ingestion/app.py`: optional read-only gateway
Add above `lifespan` and make `lifespan` return early:
```python
def ingestion_workers_enabled() -> bool:
    """`INGESTION_WORKERS_ENABLED=false` serves only the HTTP API and dashboard reads."""
return os.getenv("INGESTION_WORKERS_ENABLED", "true").strip().lower() not in {"false", "0", "no"}
@asynccontextmanager
async def lifespan(app: FastAPI):
if not ingestion_workers_enabled():
        logger.info("Ingestion workers disabled; MQTT and RabbitMQ listeners not started")
yield
return
    client = create_mqtt_client()
    # ... existing body unchanged ...
```
### 2.5 `dashboard/server.py`: timeout setting, site proxy, ask context, default mode
1. Add `import re`, and `from fastapi import Path as PathParam` on its own line (again: `pathlib.Path` is already imported as `Path`, do not shadow it).
2. Under `LIVE_BASE_URL = ...` add:
   ```python
   # The live overview runs several FHIR queries per site and the assistant runs a
   # multi-round model loop; both routinely take longer than a typical API call.
LIVE_TIMEOUT_SECONDS = float(os.getenv("OAH_LIVE_TIMEOUT_SECONDS", "90"))
MODES = {"mock", "live"}
DEFAULT_MODE = os.getenv("DASHBOARD_DEFAULT_MODE", "mock").strip().lower()
if DEFAULT_MODE not in MODES:
DEFAULT_MODE = "mock"
SITE_ID_PATTERN = r"^[A-Za-z0-9.\-]{1,64}$"
   ```
3. `get_config()` returns `{"defaultTheme": DEFAULT_THEME, "themes": THEMES, "defaultMode": DEFAULT_MODE}`.
4. In `proxy_live()`, `urlopen(request, timeout=8)` → `urlopen(request, timeout=LIVE_TIMEOUT_SECONDS)`.
5. Replace the live overview/ask routes and add the site route:
   ```python
   @app.get("/api/live/overview")
   def live_overview(refresh: bool = False) -> JSONResponse:
return proxy_live("/api/overview?refresh=true" if refresh else "/api/overview")
   @app.get("/api/live/sites/{site_id}")
   def live_site(site_id: str = PathParam(pattern=SITE_ID_PATTERN)) -> JSONResponse:
return proxy_live(f"/api/sites/{site_id}")
   # live_ingest_demo unchanged
   @app.post("/api/live/ask")
   def live_ask(payload: dict[str, Any] = Body(...)) -> JSONResponse:
       forwarded: dict[str, Any] = {"question": str(payload.get("question", ""))}
       site_id = payload.get("siteId")
if isinstance(site_id, str) and re.fullmatch(SITE_ID_PATTERN, site_id):
           forwarded["site_id"] = site_id
return proxy_live("/api/ask", method="POST", payload=forwarded)
   ```
6. `index()` returns `HTMLResponse(page.replace("__DEFAULT_THEME__", DEFAULT_THEME).replace("__DEFAULT_MODE__", DEFAULT_MODE))`.
### 2.6 `dashboard/static/index.html`
On the `<html>` tag add `data-default-mode="__DEFAULT_MODE__"`:
```html
<html lang="en" data-theme="__DEFAULT_THEME__" data-default-theme="__DEFAULT_THEME__" data-default-mode="__DEFAULT_MODE__">
```
### 2.7 `dashboard/static/js/api.js`: fix the live adapter
1. Mode selection at the top:
   ```js
   // An explicit ?mode= wins; otherwise the server's DASHBOARD_DEFAULT_MODE.
   const REQUESTED_MODE = new URLSearchParams(window.location.search).get("mode") || document.documentElement.dataset.defaultMode;
   const MODE = REQUESTED_MODE === "live" ? "live" : "mock";
   ```
2. **Delete** the module-level `let liveOverview;` and the `getLiveOverview()` helper (the gateway caches now and invalidates after uploads). Also delete the `liveOverview = ...` line that may exist inside `startRun`.
3. Replace `normalizeLiveSite` and add three helpers:
   ```js
   function normalizeLiveSite(item) {
     const siteId = item.site_id || item.id;
     const exceedances = item.exceedances || [];
     const risks = item.elevated_risks || [];
return {
       id: siteId,
       name: item.name || siteId,
       shortName: item.name || siteId,
       city: item.city ? item.city[0].toUpperCase() + item.city.slice(1) : "City not recorded",
       latitude: item.latitude,
       longitude: item.longitude,
       status: exceedances.length ? "attention" : risks.length ? "health-watch" : "observed",
       observationCount: Number(item.environmental_reading_count || 0) + Number(item.health_measure_count || 0),
       findingCount: exceedances.length + risks.length + (item.co_location ? 1 : 0),
       lastObservedAt: item.observed_at || null,
       _source: item,
     };
   }
   // The gateway carries the agency's LOW/MODERATE/HIGH reading in the unit text,
   // e.g. "{score} (HIGH)"; split it back into a unit and an interpretation.
   function splitScoreUnit(unit) {
     const match = /^(.*?)\s*\((LOW|MODERATE|HIGH)\)\s*$/.exec(unit || "");
return match ? { unit: match[1] === "{score}" ? "score" : match[1], level: match[2] } : { unit: unit === "{score}" ? "score" : unit, level: null };
   }
   function liveObservations(source, siteId) {
     const flagged = new Map((source.exceedances || []).map(item => [item.observation_id, item]));
     const environmental = (source.environmental_observations || []).map((item, index) => {
       const flag = flagged.get(item.id);
return {
         id: item.id || `live-env-${index}`, resourceRef: item.id ? `Observation/${item.id}` : null, siteId, kind: "environmental",
         indicator: item.indicator || "Environmental measure", value: item.value, unit: item.unit, codedValue: item.coded_value,
         effectiveAt: item.when,
         interpretation: flag ? `Above prototype screening value ${flag.threshold}` : item.coded_value ? "Coded survey answer" : "No screening flag raised",
         screeningReference: flag?.basis,
       };
     });
     const health = (source.health_observations || []).map((item, index) => {
       const { unit, level } = splitScoreUnit(item.unit);
return {
         id: item.id || `live-health-${index}`, resourceRef: item.id ? `Observation/${item.id}` : null, siteId, kind: "health",
         indicator: item.indicator || "Health measure", value: item.value, unit, effectiveAt: item.when,
         interpretation: level ? `Agency classification: ${level}` : "Agency classification not recorded",
         screeningReference: item.cohort ? `Cohort Group/${item.cohort}` : null,
       };
     });
return [...environmental, ...health].sort((a, b) => String(b.effectiveAt || "").localeCompare(String(a.effectiveAt || "")));
   }
   function liveFindings(source, siteId) {
     const caveat = "Prototype screening reference, not a regulatory limit.";
return [
       ...(source.exceedances || []).map((item, index) => ({
         id: `live-exceedance-${index}`, siteId, type: "threshold", severity: (item.exceedance_factor || 1) >= 2 ? "high" : "attention",
         title: `${item.indicator || "Measure"} above prototype screening value`,
         statement: `${item.value} ${item.unit || ""} against ${item.threshold}${item.exceedance_factor ? ` (${item.exceedance_factor}×)` : ""}. Basis: ${item.basis || "prototype rule"}.`,
         caveat,
       })),
       ...(source.elevated_risks || []).map((item, index) => ({
         id: `live-risk-${index}`, siteId, type: "health-watch", severity: item.interpretation === "HIGH" ? "high" : "moderate",
         title: `${item.indicator || "Health measure"} classified ${item.interpretation}`,
         statement: `Score ${item.score}${item.cohort ? ` for cohort ${item.cohort}` : ""}, as classified by the reporting agency.`,
       })),
       ...(source.co_location ? [{ id: "live-colocation", siteId, type: "co-location", severity: "attention", title: "Cross-domain co-location", statement: "An environmental screening flag and an elevated health classification share this Location.", caveat: source.caveat || "Association only, not causation." }] : []),
     ];
   }
   ```
   The field names come from `oah_agent.tools._summarize()`, which returns `id`, `indicator`, `site`, `when`, and optionally `value`, `unit`, `coded_value`, `cohort`, `statistics`. Exceedances come from `oah_ingestion.thresholds.evaluate()` (`indicator`, `value`, `unit`, `threshold`, `exceedance_factor`, `basis`) plus `observation_id`.
4. In `liveAdapter`, replace `summary` and `site`:
   ```js
   summary: async () => {
     const data = await request("/api/live/overview");
     const sites = (data.briefings || []).map(normalizeLiveSite);
     // The gateway reports these as lists of site ids, not counts.
     const countOf = value => Array.isArray(value) ? value.length : Number(value || 0);
return {
       metrics: {
         sitesInScope: data.site_count ?? sites.length,
         loadedObservations: sites.reduce((total, site) => total + site.observationCount, 0),
         screeningFindings: sites.reduce((total, site) => total + (site._source.exceedances?.length || 0), 0),
         coLocatedSites: countOf(data.sites_with_co_location),
       },
       sites,
       scopeLabel: `Dataset tag ${data.dataset_tag || "oah-demo"} on ${data.fhir_server || "the FHIR server"}`,
       countNotice: data.generated_at ? `Computed from FHIR at ${data.generated_at}; cached briefly by the gateway.` : "Computed from the tagged FHIR dataset.",
     };
   },
   site: async (_role, siteId) => {
     const source = await request(`/api/live/sites/${encodeURIComponent(siteId)}`);
return {
       site: normalizeLiveSite(source),
       observations: liveObservations(source, siteId),
       findings: liveFindings(source, siteId),
       meta: { coordinateNotice: "Coordinates come from the FHIR Location or the demo gazetteer and may be approximate.", screeningNotice: "Prototype screening rules only." },
     };
   },
   ```
5. `ask` sends the site: `ask: (_role, siteId, question) => request("/api/live/ask", { method: "POST", body: { question, siteId } }),`
6. Leave `evidence`, `graph`, `run`, `retryRun`, `reset`, `reports`, `report`, `createReport` throwing `ApiError(..., 501)` and `runs`/`startRun` as they are. Those features have no backend yet.
### 2.8 `dashboard/static/js/app.js`: two small fixes
1. In `showAbout()`, the mode-switch link must be explicit because live can now be the default:
   ```js
   const href = `${location.pathname}?mode=${targetMode}`;
   ```
2. In `renderAssistant()`, the first question chip used a hard-coded station name. Change
   `data-question="What needs attention at Mondego C1?"` to
   `data-question="What needs attention at ${escapeHtml(state.site?.site.shortName || "this site")}?"`
   (The mock assistant still matches it via the keyword "attention".)
### 2.9 Config and docs
- Append to both `.env.example` and `dashboard/.env.example`:
  ```dotenv
  # mock (fixtures) or live (reads the gateway above).
  DASHBOARD_DEFAULT_MODE=mock
  OAH_LIVE_TIMEOUT_SECONDS=90
  ```
- `README.md`, environment variable list: document `INGESTION_WORKERS_ENABLED`, `FHIR_MAX_SEARCH_RESULTS` (default 5000), `OVERVIEW_CACHE_SECONDS` (60), `OAH_BRIEFING_WORKERS` (8), `OAH_LIVE_TIMEOUT_SECONDS` (90), `DASHBOARD_DEFAULT_MODE`. In the API list, document `GET /api/overview?refresh=true`, the new `GET /api/sites/{site_id}` (404 when no observations), and `site_id` on `POST /api/ask`. In the evidence-dashboard section, state that live mode only **reads** FHIR, so already-uploaded data appears without ingestion.
- `dashboard/API-MAPPING.md`: add a row `station detail | GET /api/sites/{site_id} | ...`, change the assistant row to `{question, site_id?}`, note the site-id pattern `[A-Za-z0-9.-]{1,64}`, `OAH_LIVE_TIMEOUT_SECONDS`, and `DASHBOARD_DEFAULT_MODE`, and that `/api/config` now also returns the default mode.
## 3. Tests to add
No test may touch the network. Stub `fhir_client._request` or the agent functions with `unittest.mock`.
1. **`oah-ingestion/tests/test_fhir_client.py`** (unittest): a fake `_request` returning pages keyed by URL. Assert that (a) `search()` follows `next` across 3 pages and returns all 5 resources in order, with 3 calls; (b) `max_results=3` stops after 2 calls and returns exactly 3; (c) a `next` link equal to the current URL makes only 1 call (no infinite loop). Patch `FHIR_BASE_URL=https://fhir.test` via `mock.patch.dict("os.environ", ...)`.
2. **`oah-agent/tests/test_briefing.py`** (unittest): patch `briefing.get_site_profile`, `briefing.get_cohort`, `briefing.list_sites`. Assert that `observed_at` is the max `when`, `city == "coimbra"` for `site-c1-mondego` (from `demo/sites.json`), `co_location` is true with a nitrate 14.2 reading and a `{score} (HIGH)` health unit, the observation lists appear only with `include_observations=True`, and `dataset_briefing` copies `name`/`latitude` from `list_sites` without observation lists.
3. **`oah-ingestion/tests/test_web.py`** (unittest, call route functions directly): patch `oah_agent.briefing.dataset_briefing` / `site_briefing`, `oah_agent.tools.list_sites`, `oah_agent.assistant.ask`. Assert that gazetteer fallback fills city/lat/name, FHIR-supplied name/position win, the overview is cached (1 call for 2 requests, `refresh=True` recomputes, `invalidate_overview()` recomputes), `site_detail` calls `site_briefing(..., include_observations=True)` and raises `HTTPException(404)` when both counts are 0, and `ask` with `site_id` passes a question containing the site id while returning the original question. Call `web.invalidate_overview()` in `setUp`.
4. **`dashboard/tests/test_server.py`** (pytest; extend the existing file): import `from dashboard import server` and `from unittest import mock`. In the theme test also assert `config["defaultMode"] in {"mock","live"}`, `data-default-mode="..."` is in `index()` output, and `__DEFAULT_MODE__` is not. Add a `FakeResponse` context manager (`status`, `read()`) and tests that (a) `server.live_site("site-c1-mondego")` calls `urllib.request.urlopen` with URL `f"{server.LIVE_BASE_URL}/api/sites/site-c1-mondego"` and `timeout == server.LIVE_TIMEOUT_SECONDS` (patch it to 42.0); (b) `live_ask` forwards `site_id` only when it matches the pattern (`"../../etc/passwd"` is dropped); (c) `TestClient(server.app).get("/api/live/sites/bad%20id!")` returns 422.
Run:
```bash
python -m unittest discover -s oah-ingestion/tests -v
python -m unittest discover -s oah-pydantic-models/tests -v
python -m unittest discover -s oah-agent/tests -v
python -m pytest            # needs: python -m pip install -e ".[dev]"
```
Expected after the change: ingestion 32 tests, models 7, agent 29, dashboard 9, all passing. (One existing alerts test intentionally logs an `AttributeError` traceback; that is not a failure.)
## 4. Run it against the live data
`.env` in the repo root (example values; `APP_PORT` and `OAH_LIVE_BASE_URL` must agree):
```dotenv
APP_PORT=8001
FHIR_BASE_URL=https://hapi.fhir.org/baseR4
OAH_DATASET_TAG=oah-demo
INGESTION_WORKERS_ENABLED=false      # read-only gateway; skips MQTT/RabbitMQ
DASHBOARD_PORT=8090
OAH_LIVE_BASE_URL=http://127.0.0.1:8001
DASHBOARD_DEFAULT_MODE=live
DASHBOARD_DEFAULT_THEME=aqua
# OPENAI_API_KEY=...                 # only needed for the assistant panel
```
Terminal 1 (gateway):
```bash
cd OneAquaHealth-main && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m oah_ingestion.app
# expect: "Ingestion workers disabled; MQTT and RabbitMQ listeners not started"
```
Terminal 2 (dashboard):
```bash
cd OneAquaHealth-main && source .venv/bin/activate
python -m pip install -e ".[dev]"
oah-dashboard            # equivalent: python -m dashboard.server (run from repo root)
```
Note: `python -m oah-dashboard` does **not** work. `oah-dashboard` is a console script, not a module.
Open `http://localhost:8090` (or `http://localhost:8090/?mode=live` if `DASHBOARD_DEFAULT_MODE` is unset).
## 5. Verification checklist
1. Data exists: `curl -s "https://hapi.fhir.org/baseR4/Observation?_tag=http://hl7.eu/fhir/ig/oah/CodeSystem/dataset-tag|oah-demo&_summary=count"` should report `"total"` > 0 (it was 918).
2. Gateway overview: `curl -s http://localhost:8001/api/overview | head -c 600` returns JSON with `site_count` (was 9), `sites_with_exceedances`, `briefings[]` entries containing `city`, `observed_at`, `name`, `latitude`. The first call may take tens of seconds; repeats within 60 s are instant.
3. Station detail: `curl -s http://localhost:8001/api/sites/site-c1-mondego` includes `environmental_observations` and `health_observations`. `curl -i .../api/sites/nowhere` gives 404.
4. Through the dashboard proxy: `curl -s http://localhost:8090/api/live/overview` matches step 2, and `curl -i "http://localhost:8090/api/live/sites/bad%20id!"` gives 422.
5. In the browser: the metric tiles show **numbers** (sites, observations, screening findings, co-located sites); the station table lists all sites with a real city and timestamp; selecting Mondego C1 shows observations (pH, nitrate, zinc, health risk scores with "Agency classification: HIGH/MODERATE") and findings (threshold flags with basis, health-watch findings, co-location with the "association only" caveat).
6. Mock mode still works: `http://localhost:8090/?mode=mock`.
## 6. Troubleshooting seen in this project
- **`localhost:8090` unavailable**: the dashboard process is not running (`lsof -nP -iTCP:8090 -sTCP:LISTEN` shows nothing). Start `oah-dashboard` in its own terminal.
- **Dashboard shows "Live OneAquaHealth service unavailable" (502)**: the gateway isn't running on `OAH_LIVE_BASE_URL`, or a call took longer than `OAH_LIVE_TIMEOUT_SECONDS`. Raise the timeout or lower `FHIR_MAX_SEARCH_RESULTS`.
- **Gateway logs `AMQPConnectorSocketConnectError ... TimeoutError` for RabbitMQ**: harmless for dashboard reads. The consumer thread retries in the background. Set `INGESTION_WORKERS_ENABLED=false` to stop it. A TCP *timeout* (not "refused") means packets are dropped: when RabbitMQ runs in Docker on another Linux (Arch) laptop with `0.0.0.0:5672->5672` published, check that machine's firewall (`systemctl is-active ufw firewalld nftables`). Arch's stock `/etc/nftables.conf` has `policy drop` on the **forward** chain, which drops Docker-published ports; add `ct status dnat accept` (plus `ct state established,related accept`) to the forward chain, then `systemctl restart nftables && systemctl restart docker`. With ufw use both `ufw allow from 192.168.1.0/24 to any port 5672 proto tcp` and `ufw route allow proto tcp from 192.168.1.0/24 to any port 5672`. Also set `RABBITMQ_PASSWORD` if the broker isn't using the default `oah-local-dev`.
- **Unexpected sites** (e.g. `yam-okhla`, `mit-dharavi`): `oah-demo` is the repo's default tag on a **public** server, so other people's uploads can share it. This gateway's validation only accepts the cities coimbra/oslo/benevento/ghent/toulouse, so those records were written by something else. Use a unique `OAH_DATASET_TAG` and re-upload if you need an isolated dataset.
- **HAPI sandbox resets**: the public server is wiped occasionally. If the overview suddenly has 0 sites, re-upload with `python -m oah_demo_publishers` (needs the gateway with workers enabled) or your own loader.
## 7. Known limitations (do not try to fix unless asked)
- In live mode, Ingestion run history/retry, Evidence details, the Relationships graph, and Reports still return 501 "unavailable" by design. They need new gateway endpoints (run storage, `/api/evidence/{id}`, `/api/graph`, `/api/reports` built on `site_briefing` + `narrate`).
- There is no authentication on the gateway; dashboard personas are UI-only in live mode.
- `observed_at` uses lexical max of ISO strings, which is correct when all timestamps share an offset (the pipeline writes UTC).
- The overview cache is per-process and in-memory.