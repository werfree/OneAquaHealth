# OneAquaHealth demo-video plan — "One river, two kinds of evidence"

**Story:** the Yamuna at ITO Bridge (`yam-ito`), environmental screening evidence and population-health
surveillance viewed through a shared FHIR `Location`.

**Audience:** mixed technical / non-technical. **Target length:** 3–5 minutes (hard ceiling).

> **Governing rule — the live-data test (rev 3).** A capability is used on camera **only if it still makes
> sense when every record comes from the live FHIR server**. Nothing that exists only in the dashboard's mock
> fixtures is exercised: no mode switch to `?mode=mock`, no mock relationship graph, no mock report lifecycle,
> no mock run history/retry, no simulated persona authorization. Those features **are still classified** as
> `MOCK` / `NOT IMPLEMENTED` in §2 and §9 — they are legitimate parts of the prototype and the truth record —
> but they are **not used in the demo**. Everything the camera shows is backed by live, tagged FHIR data.
>The video runs **3–5 minutes** and the evidence dashboard stays in `?mode=live` throughout. Where a live
> capability still needs the model (Studio narration), §6 gives a deterministic live fallback.

> This document is a *recording plan and script only*. No application code, configuration, fixtures or data
> were modified to produce it. Every capability below was classified by reading the checked-out source and,
> where safe, by issuing **read-only** requests to the running services.

---

## 1. Branch and Implementation Baseline

| Item | Verified value |
|---|---|
| Requested branch | `feature/dashboard-theme-update-2` |
| Requested baseline commit | `c57157d6618065b13bde00c79018ca36ac805153` |
| **Branch actually checked out** | **`main`** — ❌ drift |
| **Inspected commit** | **`9f1cc1b9541d7c074279733ccfc7092d8d87044b`** — ❌ drift |
| Worktree state | **Dirty.** Modified: `README.md`, `dashboard/static/js/app.js`, `dashboard/static/js/studio.js`, `dashboard/static/studio.css`, `dashboard/static/styles.css`, `dashboard/tests/test_routes.mjs`, `demo/timeseries/events.json`. Untracked: `oneaquahealth-demo-video-prompt.md`. |
| Runtime verification | **Yes**, read-only, against services already running on this machine. |

### ⚠️ Drift disclosure (read first)

The task said to stop if the branch was not exactly `feature/dashboard-theme-update-2`, and not to switch
branches. The preflight found the worktree on **`main` @ `9f1cc1b`**, not the requested branch or commit. The
target branch **does exist locally** at exactly the expected baseline (`feature/dashboard-theme-update-2` →
`c57157d`), but the worktree was on `main` **with uncommitted edits** to files this task must inspect
(`dashboard/static/js/app.js`, `demo/timeseries/events.json`, `README.md`, …), so an automatic switch risked
that work. Per your explicit instruction I proceeded on `main` @ `9f1cc1b` **plus the dirty working tree**, and
treated the checked-out code as the source of truth.

**Consequences you should know:**

1. Every claim below is revalidated against `main` @ `9f1cc1b` + working tree, **not** against
   `feature/dashboard-theme-update-2`.
2. The uncommitted working tree is the source of truth for the files it touches. The one substantive
   behavioural difference in those edits is on the evidence dashboard: `app.js` now calls `render()` as soon as
   the overview summary is available, before the selected station finishes loading (progressive render); the
   Studio status chip now shows `Live / Investigating / Error` instead of `Ready / Investigating…`. The
   `officer.py` Studio lives in `oah-ingestion` and is **not** among the dirty files, so the surveillance
   backend is the committed `main` version.
3. A latent hazard in the *committed* `main` tree: `git show HEAD:README.md` contains unresolved merge-conflict
   markers (`<<<<<<< Updated upstream … >>>>>>>`). The **working tree** `README.md` has them removed (it is a
   single clean 267-line document). If you switch to the target branch, confirm `README.md` is not in that
   conflicted state before recording.

### Principal applications

| App | Entry point | Port (current `.env`) | Purpose |
|---|---|---|---|
| Ingestion gateway + Officer Studio | `python -m oah_ingestion.app` (`app.py`) | `APP_PORT=8000` | MQTT + RabbitMQ consumers, `POST /ingest`, CSV, gateway operations dashboard `/`, read API, `/api/officer/*` Studio |
| Evidence dashboard | `oah-dashboard` → `dashboard.server:main` | `DASHBOARD_PORT=8090` | Overview / Ingestion / Surveillance, `?mode=live` only for this video (mock adapter never opened) |
| District Surveillance Officer Studio (standalone) | gateway route `/api/officer/panel` | `APP_PORT` | Model-orchestrated, streamed investigations over live FHIR |
| RabbitMQ | `docker compose up -d rabbitmq` / `./run-demo.sh stack` | `5672`, UI `15672` | Citizen-survey queue |

### Chosen primary demo location and dataset

- **Location:** `yam-ito` — "Yamuna at ITO Bridge", city `delhi`, district Central Delhi, reach
  *"Yamuna — mid-city, downstream of Najafgarh drain"*, `flow_km=12`. (from `demo/sites.json`)
- **Dataset:** `meta.tag` = `<http://hl7.eu/fhir/ig/oah/CodeSystem/dataset-tag>|oah-demo-final`. The synthetic
  28-day series (`demo/timeseries/events.json`, 192 events: 168 water + 24 surveillance) is **already loaded**
  on HAPI under this tag.

### Required external dependencies

- Reachable FHIR server (`FHIR_BASE_URL=https://hapi.fhir.org/baseR4`, the shared public sandbox).
- For the Studio *narrated* investigation and executive prose: **`OPENAI_API_KEY`** and outbound access to the
  OpenAI API. Without it, station data, all analysis routes, `/report/facts`, and all exports still work.
- RabbitMQ only if a citizen-survey event is ingested live.
- Outbound MQTT (`broker.hivemq.com:1883`) only if an IoT event is ingested live.

### ✅ Dataset-tag check — resolved (was a mismatch, now correct)

Earlier the running gateway queried a stale tag (`oah-demo-sawon`) that did not contain the Indian series, so
ITO was unreachable. It has since been restarted and now reads the seeded series. Verified read-only:

| Source | `OAH_DATASET_TAG` | Observations on HAPI | Indian `yam-ito` present? |
|---|---|---|---|
| Repo `.env` (current file) | `oah-demo-final` | **908** | **Yes** |
| Gateway running on :8000 | `oah-demo-final` | 908 | **Yes** |
| Evidence dashboard proxy (:8090) | `oah-demo-final` | 908 | **Yes** |

Live confirmations:
- `GET http://127.0.0.1:8000/api/info` → `fhir.dataset_tag: "oah-demo-final"`.
- `GET http://127.0.0.1:8000/api/overview` → `site_count: 6`; `sites_with_exceedances` includes `yam-ito`.
- `GET http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28` →
  `points: 28`, `latest: 25070.0`.
- `GET http://127.0.0.1:8090/api/live/sites/yam-ito` → **HTTP 200**.

**The ITO story is recordable now.** §6.0 is therefore a **confirmation** step, not a fix. It can only regress
one way: if the gateway is restarted with a different `OAH_DATASET_TAG` than the seeded data, ITO disappears
(`points: 0`, station 404) — see §7.

---

## 2. Implementation Map

Status key: **LIVE** · **LIVE WITH LIMITATIONS** · **MOCK / SIMULATED** · **NOT IMPLEMENTED**.

| Capability | Status | Actual Implementation | Limitation / Recording Implication | Code or Data Evidence |
|---|---|---|---|---|
| Live FHIR overview | LIVE WITH LIMITATIONS | `web.overview()` → `oah_agent.briefing.dataset_briefing()`; per-site `site_briefing` → typed FHIR searches scoped by `_tag`; 60 s in-process cache | Depends on reachable FHIR + correct tag; requires gateway running with `.env` tag. Co-location flag can be `false` even when Studio finds a ward-level co-occurrence (different computation — see §3/§9). | `oah-ingestion/src/oah_ingestion/web.py` `overview()`, `_overview_cache`; `oah-agent/src/oah_agent/briefing.py` `dataset_briefing()` |
| Live station detail | LIVE WITH LIMITATIONS | `web.site_detail()` → `site_briefing(..., include_observations=True)`; 404 when no observations | Needs gateway on the story tag. Returns summarized Observations the dashboard renders. | `web.py` `site_detail()`; `briefing.py` `site_briefing()` |
| Dashboard-derived live evidence references | LIVE WITH LIMITATIONS | `api.js` `liveFinder→liveObservations/liveFindings` builds ids `live-evidence-<kind>-<i>-<site>`, `live-exceedance-*`, `live-risk-*`, `live-colocation` from the gateway payload; `liveEvidence()` regex-resolves by re-fetching the station | These are **dashboard-level references**, not stored FHIR `Evidence`. Evidence for a site is derived only from `exceedances`/`elevated_risks`/`cohorts`. | `dashboard/static/js/api.js` `liveFindings()`, `liveEvidenceId()`, `liveEvidence()` |
| Relationship graph | MOCK / SIMULATED (excluded — fails live-data test) | `server.get_graph()` reads `FIXTURE["graph"]`; live adapter throws `ApiError(…,501)` | Live mode has **no** graph endpoint. Never show the graph as live. | `dashboard/server.py` `get_graph()`; `api.js` `liveAdapter.graph` |
| Ingestion sample execution (gateway) | LIVE WITH LIMITATIONS | `web.ingest_demo(key)` loads a bundled JSON sample, validates, screens, maps, uploads via `process()`; returns `raw/validated/alert/observations/upload`; `invalidate_overview()` on `UPLOADED` | Request-scoped. Full transaction Bundle is **not** returned (only `observations[:4]`). Uploads to the shared server → duplicate/idempotent upsert. | `web.py` `ingest_demo()`, `SAMPLES`; `oah-ingestion/src/oah_ingestion/pipeline.py` `process()` |
| Durable run history | MOCK / SIMULATED (excluded — fails live-data test) | Mock `server.list_runs()`/`start_run()` over in-memory `runtime["runs"]`; live adapter returns `runs: []` from `/api/live/info` | Live mode has no durable history. Studio sessions are the only live "history", and they are in-memory. | `server.py` `list_runs()`, `start_run()`; `api.js` `liveAdapter.runs` |
| Retry workflow | MOCK / SIMULATED (excluded — fails live-data test) | Mock `server.retry_run()` creates a `retryOf` run with `forceSuccess`; live adapter throws 501 | Not live. | `server.py` `retry_run()`; `api.js` `liveAdapter.retryRun` |
| Mock report generation | MOCK / SIMULATED (excluded — fails live-data test) | `server.create_report()` → `materialize_report()` → `report_html()`/snapshot; download html/json | Live adapter throws 501 for `reports`/`report`/`createReport`. | `server.py` `create_report()`, `report_html()`; `api.js` `liveAdapter.reports` |
| Studio investigation | LIVE WITH LIMITATIONS | `officer.studio_run()` → `oah_agent.studio.run()` SSE stream; model picks typed tools; `STUDIO_SCHEMAS` | **Requires `OPENAI_API_KEY`** (see §1). Without a key the stream yields an `error` event. Sessions in-memory, expire on restart. | `oah-ingestion/src/oah_ingestion/officer.py` `studio_run()`; `oah-agent/src/oah_agent/studio.py` `run()`, `_client()` |
| Studio charts + computed analyses | LIVE | Python computes: `wards`, `trend`, `river_profile`, `persistence`, `peak_offset`; renderers in `studio-charts.js` | Live and deterministic (do **not** need a model). The *choice* of chart needs the model; the numbers do not. | `officer.py` `wards()/trend()/river_profile()/persistence()/peak_offset()`; `studio.py` `show_*`; `dashboard/static/js/studio-charts.js` |
| Studio transcript export | LIVE | `officer.studio_report(session_id)` renders the in-memory transcript to HTML | 404 after process restart ("no such session"). | `officer.py` `studio_report()`, `oah_agent.studio.session()` |
| Executive report | LIVE WITH LIMITATIONS | `officer.studio_executive()` re-structures transcript to JSON→HTML with a grounding chip | **Requires `OPENAI_API_KEY`**; deterministic `/report/facts` and `/report` (GET) also exist (the GET `/report` needs a model). | `officer.py` `studio_executive()`, `EXEC_PROMPT` |
| Deterministic report facts + live exports | LIVE | `officer.report_facts()` computes the brief with **no model**; `export_readings/surveillance/bundle.json` stream CSV/FHIR from live data | The live-data-test poster child: real, auditable, model-free. Primary fallback for any Studio scene. | `officer.py` `report_facts()`, `export_*()`; verified `readings.csv` = 140 rows, bundle = 156 entries |
| Numeric grounding | LIVE | `oah_agent.grounding.check()` extracts numbers from answer + tool results, reports unsupported figures | Deterministic, no model. Checks *presence*, not correctness; **not covered:** a grounded figure in a wrong sentence, and number-free claims (e.g. "rising"). | `oah-agent/src/oah_agent/grounding.py` `check()`; verified: supportable → `grounded=True`; `99999` → `grounded=False` |
| Persona authorization | MOCK / SIMULATED (excluded — fails live-data test) | Mock: `persona()`/`require()`/`scoped_site()` enforce per-role scope in `fixtures.json`. Live: `api.js` `capabilitySnapshot`+`LIVE_CAPABILITY_SUPPORT` express *intended* capability only | Live gateway is anonymous. Personas are **not** production auth. | `dashboard/server.py` `require()`, `scoped_site()`; `api.js` `ROLES`, `LIVE_CAPABILITY_SUPPORT` |
| MQTT ingestion | LIVE | `mqtt_worker.create_mqtt_client()` (MQTT v5, QoS 1, manual ack, persistent session); `sensor.process_packet` → `IoTEnvelope` → `process()` | Needs public broker reachability; ack withheld on upload failure. `INGESTION_WORKERS_ENABLED=false` disables it. | `oah-ingestion/src/oah_ingestion/mqtt_worker.py`; `app.py` `lifespan()` |
| RabbitMQ ingestion | LIVE | `rabbitmq_worker.consume_citizen_surveys()` on durable `ingestion.citizen_surveys`; nack/requeue logic | Needs local RabbitMQ; acks only after pipeline success. | `rabbitmq_worker.py`; `oah-ingestion/src/oah_ingestion/rabbitmq.py` |
| HTTP JSON ingestion | LIVE | `POST /ingest` (`app.ingest_event`) → 202/502/500 | Anonymous; writes to configured FHIR server. | `app.py` `ingest_event()` |
| HTTP CSV ingestion | LIVE | `POST /ingest/public-health/csv` (`app.ingest_public_health_csv`) groups rows by `event_id` | Validated before processing; per-event outcomes returned. | `app.py` `ingest_public_health_csv()`; `csv_ingestion.py` `parse_public_health_csv()` |
| Threshold screening | LIVE | `thresholds.evaluate()` city-selected (`INDIAN_CITIES`) with named bases; `alerts.assess()` pure Python | Prototype screening references, **not** statutory limits. Indian cities use CPCB/IS 10500; European cities keep nitrate-as-N/pH/zinc. | `oah-ingestion/src/oah_ingestion/thresholds.py`, `alerts.py` |
| Transaction Bundle generation | LIVE | `oah_models.fhir.bundle.to_bundle()` → dedupe by `(resourceType,id)`, `PUT <Type>/<id>` entries (idempotent upsert) | `fullUrl` only when `base_url` given. | `oah-pydantic-models/src/oah_models/fhir/bundle.py` `to_bundle()`, `dedupe()` |
| FHIR upload | LIVE | `fhir_client.upload_bundle()` POSTs to `FHIR_BASE_URL`; inspects per-entry status; transport retries (`FHIR_RETRIES`) | Writes to the shared sandbox; failures not retried at HTTP level within a broker message beyond redelivery. | `fhir_client.py` `upload_bundle()`, `_request()` |
| Dataset tagging | LIVE | `bundle.tag_resources()` stamps `meta.tag` system `…/CodeSystem/dataset-tag`, code `OAH_DATASET_TAG` | `oah-demo`/`oah-demo-*` is a **dataset scope tag only** — not a risk class or analysis result. Changing tag does not retag stored data. | `bundle.py` `tag_resources()`; `pipeline.py` `dataset_tag()` |
| Automatic dashboard refresh after ingestion | LIVE WITH LIMITATIONS | Gateway `invalidate_overview()` on `UPLOADED`; dashboard reads via `/api/live/*` | No push. The **browser** must re-navigate/refresh; no auto-refresh. | `web.py` `invalidate_overview()` |
| Production authentication | NOT IMPLEMENTED | — | Gateway anonymous; dashboard personas UI-only in live. | `HANDOVER.md`; `api.js` `liveSession()` |
| Causal / epidemiological inference | NOT IMPLEMENTED | Deliberately absent; `caveat` text on briefing, alert, offset, report | Peak offset is **descriptive only**; `health_points`=4 cannot support a correlation. | `briefing.py` `caveat`; `alerts.py` `caveat`; `officer.py` `peak_offset()` |

---

## 3. Narrative Decision

**Selected story:** *"Yamuna at ITO Bridge: environmental screening evidence and population-health surveillance
viewed through a shared FHIR `Location`."*

It is the strongest truthful story on this checkout because it is the only one where **both** evidence streams
exist for the **same** `Location`, in a **time series**, and are reachable through **live, code-computed**
analysis:

- `demo/sites.json` gives `yam-ito` a real gazetteer entry (river `Yamuna`, `flow_km`, district, reach) so the
  longitudinal profile has three ordered stations.
- The seeded series under `oah-demo-final` holds **140** environmental readings + **16** health measures for
  ITO (verified), with a deliberate, discoverable event: coliform rises, dissolved oxygen falls, and *about a
  week later* acute diarrhoeal disease notifications rise.
- The Python analyses that carry the story are all **deterministic and verified live**: trend (14-day mean
  change **+84.9 %**), ward ranking (`priority: ['yam-ito']`, ADD **+140.4 %**), river profile (largest step
  **Wazirabad → ITO, 32.84× over 12 km**), persistence (**28/28** days), and an offset of **+9 days** with an
  explicit "descriptive, not a correlation" caveat.
- The pipeline that produced those records is fully traceable in code and was exercised end-to-end with upload
  disabled: the ITO sample screens **HIGH** (coliform 84 802 MPN/100 mL = 33.92× the 2 500 criterion; BOD
  16.8 mg/L; DO 0.9 mg/L; NH₃-N 5.6 mg/L) and maps to `Device×1, Observation×5, Location×5, Specimen×5`.

**Selection rule — the live-data test.** The constraint is explicit: we will not use anything that does not
make sense without live data. Applied here, a capability earns a place on camera only if every record it
displays comes from the live FHIR server. Two consequences:

- **Kept** — anything live-backed: the gateway overview and station detail; the dashboard's derived evidence
  references; the Officer Studio's deterministic analyses (`wards`, `trend`, `river_profile`, `persistence`,
  `peak_offset`); the deterministic `/api/officer/report/facts` brief; the live CSV and FHIR-Bundle exports;
  the ingestion pipeline; and the MQTT / RabbitMQ / HTTP channels. The Studio's model-narrated investigation is
  kept too, because it *reads live FHIR* — it only needs `OPENAI_API_KEY`, and §6 gives a deterministic live
  fallback when the key is absent.
- **Excluded** — anything that lives only in the dashboard's mock fixtures or has no live endpoint: the
  relationship graph, the mock report lifecycle, mock run history/retry, and simulated persona authorization.
  These do **not** make sense without mock data, so the camera never opens them and never switches to
  `?mode=mock`. They stay classified as `MOCK` / `NOT IMPLEMENTED` in §2 and §9 as an honest record of the
  system's boundaries — classification is documentation, not a demo asset.

The mock/live boundary is therefore stated once, in words, in the close (Scene 9) — not demonstrated on
screen.

**Non-negotiable scientific boundary carried throughout:** co-location, a temporal offset, and parallel trends
justify *investigation*; they do not establish that river conditions caused the reported health pattern. The
scenario is synthetic demonstration data.

**One honesty trap the storyboard navigates deliberately:** the *evidence dashboard* only raises its
"Cross-domain co-location" finding when a site has **both** an exceedance **and** an `elevated_risk`. For the
synthetic Indian series there are **no** `risk_scores`, so `sites_with_co_location` is empty and the dashboard
co-location finding never appears. The *Studio* uses a different definition (an exceedance **and** a >15 % rise
in notified ADD), which is why it reports `yam-ito` as co-located. The narration states both plainly rather
than implying the dashboard tile confirms the Studio finding.

---

## 4. Detailed 3–5 Minute Storyboard (live only)

Assumed state: gateway restarted so `OAH_DATASET_TAG=oah-demo-final` (§6 Preflight). Two terminals arranged
side by side (Terminal A = gateway logs, Terminal B = shell). Browser is **always** on
`http://127.0.0.1:8090/?mode=live`. **No mock scene is recorded;** the dashboard's mock deck is never opened.

Scene numbering below is sequential for the shortened cut (0–9). Old scene numbers are noted where a scene was
merged or removed. **The `Live/Mock Status` column reads `LIVE` or `LIVE WITH LIMITATIONS` only.**

### Scene 0 — Cold open title card (0:00–0:10)

| Field | Detail |
|---|---|
| Time | 0:00–0:10 |
| Scene | Opening title |
| Screen / Visual | Full-screen title card (see §8): title "One river, two kinds of evidence"; subtitle "Yamuna at ITO Bridge — synthetic demonstration dataset"; small strip "Environmental measurements · Notified population health · HL7 FHIR R4". Below it, a still of the browser address `http://127.0.0.1:8090/?mode=live`. |
| Presenter Action | Stand/face camera over the card. |
| Narration | "One location on the Yamuna. Two completely different kinds of evidence. And one question: what does the evidence actually support?" |
| Technical Event | None. |
| Live/Mock Status | LIVE (browser is in live mode). |
| Evidence / Code Source | `dashboard/static/js/api.js` `REQUESTED_MODE`; `DEFAULT_MODE=live` from `.env` via `server.get_config()`. |

### Scene 1 — Establish one investigation, one station (0:10–0:32)

| Field | Detail |
|---|---|
| Time | 0:10–0:32 |
| Scene | Overview; scope and mode |
| Screen / Visual | Browser at `http://127.0.0.1:8090/?mode=live`. Top bar shows the **mode indicator** (live → `Live adapter`) and the **Current station** selector set to **Yamuna at ITO Bridge**. Left sidebar: Overview / Ingestion / Reports / Surveillance. Overview metric tiles: **sites in scope**, **loaded observations**, **screening findings**, **co-located sites**. Under the tiles, the scope line: `Dataset tag oah-demo-final on https://hapi.fhir.org/baseR4`. |
| Presenter Action | Point at the mode indicator, then at the station selector. Zoom/callout on the scope line. |
| Narration | "We're not touring features. This is one investigation of one place — the Yamuna at ITO Bridge, in Delhi. Everything you're about to see is read live from a FHIR server, scoped to a single dataset tag. The tag is how we know these records are ours on a server that many people share." |
| Technical Event | `GET /api/live/overview` → `dashboard/server.py live_overview()` → gateway `GET /api/overview` → `dataset_briefing(tag)`. |
| Live/Mock Status | LIVE WITH LIMITATIONS (needs reachable FHIR + a gateway on the right tag). |
| Evidence / Code Source | `web.overview()`, `_with_site_details()`; `briefing.dataset_briefing()`; `api.js` `liveAdapter.summary`. |

### Scene 2 — Two kinds of evidence at one Location (0:32–1:02)

| Field | Detail |
|---|---|
| Time | 0:32–1:02 |
| Scene | Station workspace → **Context** |
| Screen / Visual | Station `yam-ito` selected. The workspace opens on the **Context** tab (tabs are labelled **Context / Evidence / Relationships**). The observations table lists environmental readings — faecal coliform, BOD, dissolved oxygen — and health measures (acute diarrhoeal disease) — with effective dates. Callout the shared Location and the differing time cadence (daily water vs weekly health). |
| Presenter Action | Scroll the observations. Highlight a coliform row and an ADD row. Point out that both cite the **same** Location. |
| Narration | "Same place, two kinds of evidence. Above the line: water the environment agency measured — faecal coliform, BOD, oxygen. Below it: case counts the health system notified — acute diarrhoeal disease. Notice they don't arrive on the same clock: the water is measured daily, the cases are reported weekly. That difference matters later, so keep it in mind." |
| Technical Event | `GET /api/live/sites/yam-ito` → gateway `GET /api/sites/yam-ito` → `site_briefing(include_observations=True)`. |
| Live/Mock Status | LIVE WITH LIMITATIONS. |
| Evidence / Code Source | `web.site_detail()`; `briefing.site_briefing()`; `tools.search_observations()`; `api.js` `liveObservations()`. |

### Scene 3 — What deserves attention (1:02–1:28)

| Field | Detail |
|---|---|
| Time | 1:02–1:28 |
| Scene | Findings → **Evidence** tab |
| Screen / Visual | Click **Evidence**. Threshold findings such as "Faecal coliform above prototype screening value — 25 070 MPN/100 mL against 2 500 (≈10×). Basis: CPCB Primary Water Quality Criteria for Bathing Waters…". Open the **evidence drawer** for one finding to show the two derived records: a `FHIR_OBSERVATION` (the flagged reading) and a `THRESHOLD_RULE` (the screening basis). |
| Presenter Action | Open the drawer; callout the record **types** and the `live-evidence-…` id. |
| Narration | "The dashboard surfaces what deserves attention: a reading above a screening reference. Open it and you get two things — the actual FHIR Observation that was measured, and the rule it was screened against, with its stated basis. That `live-evidence-…` reference is a dashboard-level link built from the station data; the underlying record really is a FHIR Observation on the server. The rule is where the number '2 500' comes from — it's the CPCB bathing-water criterion, quoted, not recalled." |
| Technical Event | `api.js liveFindings()` builds `live-exceedance-*` + `live-evidence-(exceedance|rule)-…`; drawer resolver `liveEvidence()` re-fetches the station. |
| Live/Mock Status | LIVE WITH LIMITATIONS (derived dashboard references; underlying records are real FHIR Observations). |
| Evidence / Code Source | `api.js liveFindings()/liveEvidence()/liveEvidenceRecord()`; `thresholds.INDIAN_THRESHOLDS`; `briefing._exceedances()`. |

> **Do not click the Relationships tab.** It is mock-only in live mode and is **excluded from this video**. Stay
> on Context and Evidence. (The tab bar renders all three labels, so the tabs are visible on screen — just never
> open Relationships.)

### Scene 4 — A deliberate boundary callout (1:28–1:38)

| Field | Detail |
|---|---|
| Time | 1:28–1:38 |
| Scene | On-screen title card / lower-third |
| Screen / Visual | A restrained lower-third card over the frozen Evidence view: **"Co-location is not causation."** Sub-line: *"These are co-located synthetic records. A shared Location, a temporal offset, and parallel trends justify investigation — they do not establish that river conditions caused the health pattern."* |
| Presenter Action | Pause on the card. |
| Narration | "Before we go further: everything here is one shared place. Co-location is not causation. Hold that." |
| Technical Event | None (card). |
| Live/Mock Status | n/a (narration boundary). |
| Evidence / Code Source | `briefing.site_briefing()` `caveat`; `alerts.assess()` `caveat`; `README.md` "Screening and interpretation". |

### Scene 5 — Is it isolated or sustained? Where along the river? (1:38–2:08)

| Field | Detail |
|---|---|
| Time | 1:38–2:08 |
| Scene | Open Surveillance Studio from the dashboard → run the ITO investigation |
| Screen / Visual | In live mode, the assistant panel shows the button **"Open Surveillance Studio"** (it appears only in live mode). Click it. Studio opens (dashboard `/studio`, or the gateway `/api/officer/panel`). Scope selector: **Current station** / **All stations** — choose **Current station** (Yamuna at ITO Bridge). Type the exact prompt: `Investigate the Yamuna at ITO Bridge over the last month.` and press **Run**. |
| Presenter Action | Read the prompt aloud as you type it. Let the run start. |
| Narration | "Let's ask two questions a surveillance officer actually asks: is this a one-off, or is it sustained — and does it look the same everywhere on the river, or is there a pattern along it? I'll investigate ITO over the last month." |
| Technical Event | `POST /api/live/studio/run` → dashboard `live_studio_run()` → gateway `POST /api/officer/studio/run` → `oah_agent.studio.run()` (SSE). Dashboard appends station context to the question. |
| Live/Mock Status | LIVE WITH LIMITATIONS (**requires `OPENAI_API_KEY`**; sessions in memory). |
| Evidence / Code Source | `app.js renderAssistant()` ("Open Surveillance Studio"); `officer.py studio_run()`; `studio.py run()`, `SYSTEM`; `server.py live_studio_run()`. |

> If no OpenAI key is available, **substitute** by showing the deterministic routes directly (see §6.1 model
> access and the §7 "OpenAI key / model availability" row): the charts and all five analyses still render from
> Python; only the model's tool *choices* are missing.

### Scene 6 — Watch the work happen (2:08–2:45)

| Field | Detail |
|---|---|
| Time | 2:08–2:45 |
| Scene | Studio streaming: tools, charts, answer, grounding |
| Screen / Visual | As the run streams: a reasoning line, then tool chips (e.g. **get_thresholds**, **rank_wards**, **show_trend**, **show_river_profile**, **show_persistence**), each expandable to show the exact **FHIR queries run**. A **trend** chart with two aligned panels (coliform above, notified ADD below). A **river profile** for the Yamuna: Wazirabad → ITO → Okhla. A **persistence** strip. Finally an answer with a **grounding chip** (✓ Grounded — *n* figures verified against *m* retrieved). |
| Presenter Action | Expand exactly one tool to reveal its query URL. Point at the profile's steep step. Do **not** hover-tooltip "correlation". |
| Narration | "Watch what it does. It fetches the screening criteria first — deliberately, so it never quotes a threshold from memory. It ranks the wards, then it draws the river in flow order: Wazirabad upstream, then ITO, then Okhla. See the step between the first two — that's where the load appears on this reach. And the persistence strip answers 'one-off or sustained': for ITO it's sustained across the window. Every figure in that answer is checked against the data the tools actually returned, and the receipt is the green chip." |
| Technical Event | SSE events `start → thinking → tool_start/tool_done → render → answer → done`; charts via `createChartRenderer`. |
| Live/Mock Status | LIVE (deterministic tool data) + model narration via OpenAI. |
| Evidence / Code Source | `studio.py run()` (tool loop, `_render`), `show_trend()/show_river_profile()/show_persistence()`; `officer.py trend()/river_profile()/persistence()`; `grounding.check()`; `studio-charts.js`. |

**Verified numbers you may quote (all from `oah-demo-final`, read-only):**

| Quantity | Value |
|---|---|
| ITO coliform, latest | **25 070 MPN/100 mL** vs criterion **2 500** → **10.03×** |
| ITO coliform, 14-day change | recent mean **37 775.21** vs prior **20 433.36** → **+84.9 %** |
| Ward priority | `['yam-ito']`; ADD change **+140.4 %** (Okhla −6.4 %, Dharavi −10.3 %) |
| Yamuna profile | Wazirabad mean **886** (within) → ITO **29 104** (**11.64×**) → Okhla **33 127** (**13.25×**); largest step **32.84× over 12 km** |
| Persistence (coliform) | yam-ito **28/28** days over; longest run **28** |
| Descriptive peak offset | water peak 2026-09-24, health peak 2026-10-03 → **+9 days**; **4** weekly health points |

### Scene 7 — The honest chart and the honest label (2:45–3:08)

| Field | Detail |
|---|---|
| Time | 2:45–3:08 |
| Scene | Descriptive peak offset (live only) |
| Screen / Visual | If the Studio investigation surfaced the offset, show the offset statement: *"The notified-case peak falls 9 days after the water peak."* with its caveat rendered beside it. **No mode toggle, no graph, no report.** If the run did not surface it, show the same value from the deterministic route in Terminal B: `curl -s "http://127.0.0.1:8000/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28"` — highlighting `offset_days: 9`, `health_points: 4`, and the `caveat` string. |
| Presenter Action | Read the caveat aloud, word for word. Do **not** hover or say the word "correlation". |
| Narration | "Here's the part I'd stake the project on. The gap between the two peaks is nine days — but look at what it calls itself: a *descriptive offset between two maxima, not a correlation*. In this window there are only four weekly case reports. You cannot compute a meaningful correlation from four points, and the software says so instead of pretending. That is the honesty I mean." |
| Technical Event | `officer.peak_offset()` (`caveat`, `health_points`); `studio.peak_offset()` tool. |
| Live/Mock Status | LIVE (deterministic, no model needed for the number). |
| Evidence / Code Source | `officer.py peak_offset()`; `studio.py peak_offset()`. |

### Scene 8 — Where did these records come from? (3:08–3:55)

| Field | Detail |
|---|---|
| Time | 3:08–3:55 |
| Scene | Ingestion: trace one source event end to end |
| Screen / Visual | Terminal A shows the gateway. Terminal B runs the supplied ITO sample through the **real** pipeline. Expected output: the `[HIGH] yam-ito (delhi)` alert with four exceedances (coliform **84 802** = **33.92×**, BOD **16.8**, oxygen **0.9**, NH₃-N **5.6**), then the mapped resource counts. Then the gateway's own dashboard/`/api/ingest-demo/iot` stage view (Received → Validated → Screened → Mapped → Bundled → Upsert). |
| Presenter Action | Run the command in Terminal B; point at the alert block, then at the resource counts. |
| Narration | "So where did those ITO records come from? Let's send one reading down the real path. Watch the stages: the raw payload is validated into a typed envelope, screened against the prototype references *before* any conversion — so an exceedance is raised even if the server is down — then mapped to FHIR, tagged with the dataset tag, wrapped in a transaction Bundle, and uploaded. Here the same reading raises a HIGH alert, and you can see the resources it becomes: a Device, Observations, Locations, Specimens. That's the identical code path a real sensor or a broker message takes." |
| Technical Event | `process()` → `raise_for` (screen) → `envelope_to_fhir` (map) → `tag_resources` → `to_bundle` → `upload_bundle`. Run with `FHIR_UPLOAD_ENABLED=false` if you must not write to the shared server (result `BUILT_NOT_SENT`) — see §6. |
| Live/Mock Status | LIVE (deterministic). |
| Evidence / Code Source | `pipeline.py process()`; `alerts.py assess()/format_alert()`; `fhir_adapter.py iot_to_fhir()`; `bundle.py to_bundle()/tag_resources()`; `fhir_client.upload_bundle()`; `web.py ingest_demo()`. |

### Scene 9 — Three doors, one pipeline; close the loop (3:55–4:30)

| Field | Detail |
|---|---|
| Time | 3:55–4:30 |
| Scene | Ingestion channels converge → back to the evidence view → end card |
| Screen / Visual | A simple convergence graphic (§8): three labelled inputs — **IoT telemetry (MQTT)**, **Citizen survey (RabbitMQ)**, **Public health (HTTP / CSV)** — funnel into one arrow: **shared pipeline → tagged FHIR transaction Bundle**. Overlay real identifiers: `MQTT_TOPIC=oneaquahealth/sensors/+/+`, queue `ingestion.citizen_surveys`, `POST /ingest`, `POST /ingest/public-health/csv`. Then cut back to `http://127.0.0.1:8090/?mode=live` on `yam-ito` (refresh **F5**, re-open **Context**). End on a slate with the value sentence and the synthetic-data disclosure. |
| Presenter Action | Trace the three arrows, then refresh deliberately and say why. Hold on the end slate. |
| Narration | "Sensors arrive over MQTT. Volunteer surveys arrive over a message queue. Public-health returns arrive over HTTP, as JSON or as a CSV batch. Different transports — but once inside, the same validation, the same screening, the same FHIR mapping, and the same tagged, idempotent upload. That's what makes water evidence and health evidence land in one interoperable store. [refresh] Back where we started — same location, same two kinds of evidence, but now we know where every record came from and how far the evidence lets us go. Everything you've seen came from live records: we used only what still makes sense with live data, and left the prototype's mock-only screens — the richer relationship graph, the report workflow, the demo personas — out of the cut. OneAquaHealth makes heterogeneous environmental and population-health evidence interoperable, visible and traceable — while staying honest about what it cannot establish. Synthetic data, prototype screening references. Co-located records, a descriptive pattern, a signal worth investigating — not causation. Confirmatory sampling is the next step, and that decision stays with the officer." |
| Technical Event | `mqtt_worker`, `rabbitmq_worker`, `app.ingest_event/ingest_public_health_csv` all call `pipeline.process()`; `GET /api/live/sites/yam-ito` after refresh. |
| Live/Mock Status | LIVE. |
| Evidence / Code Source | `mqtt_worker.py`; `rabbitmq_worker.py`; `app.py`; `pipeline.py`; `web.site_detail()`; `web.invalidate_overview()`; `demo/generate_timeseries.py` docstring; `thresholds.as_reference()` note; `README.md`. |

**Total ≈ 4 min 30 s** (within the 3–5 minute ceiling). If the Studio run is slow on the day, cut the
`show_persistence` mention in Scene 6 and trim Scene 7 to the caveat alone to land nearer 4:00. If you need to
trim further, merge Scene 4's boundary card into Scene 3's narration.

---

## 5. Complete Presenter Script

> Spoken narration only. Stage directions in *[brackets]*. Read at a steady pace.

*[Title card: "One river, two kinds of evidence."]*

**0:00** One location on the Yamuna. Two completely different kinds of evidence. And one question: what does
the evidence actually support?

*[Open `http://127.0.0.1:8090/?mode=live`.]*

**0:10** We're not touring features. This is one investigation of one place — the Yamuna at ITO Bridge, in
Delhi. *[point at the mode indicator]* The dashboard is in live mode, and everything you're about to see is
read live from a FHIR server, scoped to a single dataset tag. *[point at the scope line]* That tag is how we
know these records are ours on a server that many people share.

*[Station is "Yamuna at ITO Bridge"; Context tab.]*

**0:32** Same place, two kinds of evidence. Above the line: water the environment agency measured — faecal
coliform, BOD, oxygen. Below it: case counts the health system notified — acute diarrhoeal disease. Notice
they don't arrive on the same clock. The water is measured daily; the cases are reported weekly. That
difference matters in a moment, so keep it in mind.

*[Click Evidence; open one finding's drawer.]*

**1:02** The dashboard surfaces what deserves attention: a reading above a screening reference. Open it and
you get two things — the actual FHIR Observation that was measured, and the rule it was screened against, with
its stated basis. That "live-evidence" reference is a dashboard-level link built from the station data; the
record underneath really is a FHIR Observation on the server. And the "2 500" you see is the CPCB bathing
water criterion — quoted from the code, not recalled by a model.

*[Hold on the boundary card.]*

**1:28** Before we go further: everything here is one shared place. Co-location is not causation. Hold that.

*[Click "Open Surveillance Studio"; scope = Current station; type the prompt; Run.]*

**1:38** Let's ask two questions a surveillance officer actually asks. Is this a one-off, or is it sustained?
And does it look the same everywhere on the river, or is there a pattern along it? I'll investigate ITO over
the last month. *[type]* "Investigate the Yamuna at ITO Bridge over the last month."

*[Watch the stream.]*

**2:08** Watch what it does. It fetches the screening criteria first — deliberately, so it never quotes a
threshold from memory. It ranks the wards, then it draws the river in flow order: Wazirabad upstream, then
ITO, then Okhla. *[point at the step]* See the step between the first two — that's where the load appears on
this reach. And the persistence strip answers "one-off or sustained": for ITO, it's sustained across the
window. Every figure in that answer is checked against the data the tools actually returned, and the receipt
is the green chip.

*[Offset statement and caveat on screen.]*

**2:45** Here's the part I'd stake the project on. The gap between the two peaks is nine days — but look at
what it calls itself: a *descriptive offset between two maxima, not a correlation*. In this window there are
only four weekly case reports. You cannot compute a meaningful correlation from four points, and the software
says so instead of pretending. That is the honesty I mean.

*[Terminal: run the ITO sample.]*

**3:08** So where did those ITO records come from? Let's send one reading down the real path. Watch the
stages: the raw payload is validated into a typed envelope, screened against the prototype references *before*
any conversion — so an exceedance is raised even if the server is unreachable — then mapped to FHIR, tagged
with the dataset tag, wrapped in a transaction Bundle, and uploaded. Here the same reading raises a HIGH alert,
and you can see the resources it becomes: a Device, Observations, Locations, Specimens. That's the identical
code path a real sensor or a broker message takes.

*[Convergence graphic, then back to live `yam-ito`; refresh.]*

**3:55** Sensors arrive over MQTT. Volunteer surveys arrive over a message queue. Public-health returns
arrive over HTTP, as JSON or as a CSV batch. Different transports — but once inside, the same validation, the
same screening, the same FHIR mapping, and the same tagged, idempotent upload. That's what makes water
evidence and health evidence land in one interoperable store. *[refresh]* Back where we started — same
location, same two kinds of evidence, but now we know where every record came from and how far the evidence
lets us go. Everything you've seen came from live records: we used only what still makes sense with live data,
and left the prototype's mock-only screens out of the cut. OneAquaHealth makes heterogeneous environmental
and population-health evidence interoperable, visible and traceable — while staying honest about what it cannot
establish. Synthetic data, prototype screening references, and a shared demo server — the method is real, the
readings are not. Co-located records, a descriptive pattern, a signal worth investigating. Not causation.
Confirmatory sampling is the next step, and that decision stays with the officer.

*[End card.]*

**4:30** One river. Two kinds of evidence. A signal worth investigating — and the discipline to say only that.
Thanks for watching.

---

## 6. Recording Runbook

All commands are repository-grounded. Terminals: **A** = gateway, **B** = shell/ingestion, **C** = dashboard.
Use the repo virtualenv (`/.venv`, Python 3.14) which already has `openai` 3.23.0 and `oah-dashboard` installed.

### 6.0 Preflight: confirm the dataset tag matches the seeded series (already correct)

The running gateway **now uses `oah-demo-final`** and sees the ITO data. This preflight is a **confirmation,
not a fix** — run it before every session so the tag cannot silently drift. **No re-seeding, no writes.**

```bash
# 1. Confirm what the running gateway is actually querying (must be oah-demo-final)
curl -s http://127.0.0.1:8000/api/info | grep -o '"dataset_tag": *"[^"]*"'
# expect: "dataset_tag": "oah-demo-final"

# 2. Confirm the repo .env points at the seeded series

grep '^OAH_DATASET_TAG' .env
# expect: OAH_DATASET_TAG=oah-demo-final

# 3. Confirm the seeded ITO series exists on HAPI (read-only)
curl -s "https://hapi.fhir.org/baseR4/Observation?_tag=http://hl7.eu/fhir/ig/oah/CodeSystem/dataset-tag|oah-demo-final&_summary=count"
# expect: {"resourceType":"Bundle","total":908,...}   (read-only; no write)
```

**Only if step 1 returns a different tag**, the gateway was started with a stale environment. Restart it so it
reloads `.env` (`load_dotenv()` runs at import in `app.py`). In Terminal A stop the old process (Ctrl-C or
kill its PID), then:

```bash
python3 -m oah_ingestion.app     # loads .env: OAH_DATASET_TAG=oah-demo-final, APP_PORT=8000
# or, to skip MQTT/RabbitMQ consumers for a quieter read-only recording:
#   INGESTION_WORKERS_ENABLED=false python3 -m oah_ingestion.app
```

Then re-verify before any recording:

```bash
curl -s http://127.0.0.1:8000/api/info | grep -o '"dataset_tag": *"[^"]*"'      # -> oah-demo-final
curl -s "http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28" \
  | .venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print('points',d['points'],'latest',d['latest'])"
# expect: points 28 latest 25070.0
```

### 6.1 Environment (`.env`) — no secrets exposed here

Required in the repo-root `.env` (values verified consistent):

```dotenv
APP_HOST=0.0.0.0
APP_PORT=8000
FHIR_BASE_URL=https://hapi.fhir.org/baseR4
FHIR_UPLOAD_ENABLED=true          # set false for a no-write recording (see 6.6)
OAH_DATASET_TAG=oah-demo-final    # MUST match seeded data; restart gateway after changing
OAH_CITIES=delhi,kanpur,varanasi,mumbai,chennai,hyderabad
OAH_SITES_FILE=demo/sites.json
MQTT_HOST=broker.hivemq.com
MQTT_PORT=1883
MQTT_TOPIC=oneaquahealth/sensors/+/+
MQTT_CLIENT_ID=OAHIngest-recording   # keep stable across restarts
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=oah
RABBITMQ_PASSWORD=oah-local-dev
DASHBOARD_PORT=8090
OAH_LIVE_BASE_URL=http://127.0.0.1:8000
DASHBOARD_DEFAULT_MODE=live
DASHBOARD_DEFAULT_THEME=aqua
```

Model access — **the only non-live dependency in the cut**, and it is live-data-gated:
- The deterministic live routes need **no key**: `wards`, `trend`, `profile`, `persistence`, `offset`,
  `/report/facts`, and all exports read live FHIR and compute in Python. **Prefer these when unsure.**
- The Studio's streamed investigation **reads live FHIR** but uses the model to choose tools and write prose.
  It requires **`OPENAI_API_KEY`** and outbound access to the OpenAI API.
- ⚠️ On this checkout the code calls the **OpenAI SDK directly** (`assistant._client()` / `studio._client()`);
  there is **no `llm.py`** and the `.env` values `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` are
  **ignored by the code**. Setting them does not route the Studio to Ollama — that wiring does not exist on
  this branch. `OPENAI_MODEL` defaults to `gpt-4o` (`studio.DEFAULT_MODEL`).
- If no key is available, do **not** show a stuck "Investigating" panel. Record the deterministic live routes
  instead (they satisfy the live-data test with no model at all), or pre-record a good Studio run and cut it in.

> Do not paste secrets on camera. Blur or pre-set the key before recording.

### 6.2 Dependencies

Assumed already installed. If starting fresh:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt     # oah-ingestion + oah-agent
.venv/bin/python -m pip install -e ".[dev]"            # oah-dashboard + dev deps
```

`run-demo.sh` also works with no install (it sets `PYTHONPATH=…/src`), but it uses `python3` and the repo
`src` trees.

### 6.3 RabbitMQ (only if you ingest a citizen survey live)

```bash
./run-demo.sh stack          # docker run oah-rabbitmq, port 5672 + 15672, waits for ping
# or: docker compose up -d rabbitmq
```
Not needed for the ITO water/health story. Keep the terminal open if you use it.

### 6.4 Gateway (Terminal A)

```bash
python3 -m oah_ingestion.app
```
Expected log lines: `Loaded 17 sites from …/demo/sites.json`; with workers on, `Starting MQTT sensor listener
for broker.hivemq.com:1883` and `Consuming citizen surveys from ingestion.citizen_surveys`. If you set
`INGESTION_WORKERS_ENABLED=false`: `Ingestion workers disabled; MQTT and RabbitMQ listeners not started`.

### 6.5 Dashboard (Terminal C)

```bash
oah-dashboard                 # console script -> dashboard.server:main   (port 8090)
# note: `python -m oah-dashboard` does NOT work; use the console script.
```
Open **`http://127.0.0.1:8090/?mode=live`** (explicit `?mode=live` wins over `DASHBOARD_DEFAULT_MODE`).

### 6.6 FHIR prerequisites and the "no-write" option

- The story needs the already-seeded `oah-demo-final` dataset (908 Observations). **Do not re-seed to record.**
- If you want to demonstrate a *write* (Scene 8), prefer one of:
  1. **`FHIR_UPLOAD_ENABLED=false`** — the pipeline still validates, screens, maps and builds the Bundle and
     returns `BUILT_NOT_SENT`; nothing is written. Log shows `FHIR upload disabled; built {…} (not sent)`.
  2. A **uniquely scoped tag** (`OAH_DATASET_TAG=oah-demo-<yourname>-<date>`) if you must show a real upload,
     so your writes never mix with anyone else's `oah-demo*` data.
  3. Your own FHIR server via `FHIR_BASE_URL`.
- Avoid `./run-demo.sh seed` for the video: it re-uploads 192 events to the shared sandbox (and dates are
  relative to the current date — see §7).

### 6.7 Time-series seeding strategy (already done — do not repeat to record)

The series already exists under `oah-demo-final`. If you ever need to regenerate, know that
`demo/generate_timeseries.py` anchors dates to **now** (`datetime.now(timezone.utc) - timedelta(days=days)`),
so regenerating shifts every date and will not match the numbers in §4:

```bash
python3 demo/generate_timeseries.py --days 28            # write JSON only, no network
python3 demo/generate_timeseries.py --days 28 --ingest   # also upload (writes to the sandbox)
./run-demo.sh seed                                       # equivalent direct seed
```

### 6.8 Exact Studio prompt and sample to run

- **Studio prompt (Scene 5):** `Investigate the Yamuna at ITO Bridge over the last month.` Scope = **Current
  station**. (The dashboard appends `Dashboard context: investigate station yam-ito…` automatically.)
- **Ingestion sample (Scene 8):** key **`iot`** — "Yamuna at ITO Bridge: coliform with statistics, BOD,
  dissolved oxygen". Via the gateway dashboard's stage UI or:

```bash
# through the gateway (writes unless FHIR_UPLOAD_ENABLED=false):
curl -s -X POST http://127.0.0.1:8000/api/ingest-demo/iot | .venv/bin/python -m json.tool | head -40
```

### 6.9 Expected logs and response states

| Where | Expected |
|---|---|
| Gateway, on `POST /api/ingest-demo/iot` | `[HIGH] yam-ito (delhi) …` alert with coliform 84802 (33.92×), bod 16.8 (5.6×), dissolved_oxygen 0.9 (5.56×), ammoniacal_nitrogen 5.6 (4.67×); then `FHIR upload -> … N/N resource(s) uploaded` |
| `POST /api/ingest-demo/iot` response | `ok:true`, `validated.source_type=IOT_TELEMETRY`, `alert.severity=HIGH`, `profiles` includes `observation-with-component-oah`, `upload.fhir=UPLOADED` (or `BUILT_NOT_SENT` if disabled) |
| Studio run (SSE) | `start → thinking → tool_start/tool_done → render → answer → done`; final `answer.grounding.grounded=true` |
| `/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28` | `points 28`, `latest 25070.0`, `exceedance_factor 10.03` |
| `/api/officer/wards?days=28` | `priority ["yam-ito"]`, `co_located true`, `add_change_pct 140.4` |
| `/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28` | largest step Wazirabad→ITO `ratio 32.84`, `reach_km 12` |
| `/api/officer/offset?site_id=yam-ito&days=28` | `offset_days 9`, `health_points 4`, caveat "not a correlation" |

### 6.10 Refresh / cache handling (Scene 9)

- The gateway overview is cached `OVERVIEW_CACHE_SECONDS=60` in process memory (`web._overview_cache`).
- After an ingestion that returns `UPLOADED`, `web.invalidate_overview()` clears it automatically.
- The dashboard does **not** auto-refresh: re-navigate or **F5**, or call
  `GET /api/live/overview?refresh=true`. A hard refresh also clears `api.js`'s per-station `liveStationCache`.
- **Note:** in live mode a station page opened *cold* (deep link) re-fetches from the gateway.

### 6.11 Studio download steps (optional — not required for the 3–5 min cut)

Downloads are optional and **not needed** for a 3–5 minute video. If you choose to show one, keep it to a
single shot:

- Transcript: `GET /api/live/studio/transcript/{session}` (dashboard) → `GET /api/officer/studio/report/{session}`
  (gateway) — HTML download `investigation-<session>.html`.
- Executive: click **Executive report (PDF)** → `POST /api/live/studio/executive` → HTML; open and print to PDF.
- Exports: `GET /api/live/studio/export/{readings|surveillance|fhir}?days=28&site_id=yam-ito`.
  Verified locally: `readings.csv` = 140 rows (`oah-readings-yam-ito-28d.csv`); FHIR export = a `collection`
  Bundle, `total 156`, tagged `oah-demo-final`.
- Sessions are **in memory**: after a gateway restart, transcript/executive return 404 ("no such session").

### 6.12 Reset and recovery

```bash
./run-demo.sh down            # stop RabbitMQ
# restart gateway to reload env / clear overview cache / drop Studio sessions
```
If a scene fails: refresh the browser (F5), then re-run the gateway endpoint via `curl` to confirm the backend
is healthy before blaming the UI. **Do not switch the browser to `?mode=mock` to recover** — this cut is
live-only; if a live scene will not load, use the equivalent `curl` fallback shown in the scene table instead.

---

## 7. Demo Risk Checklist

| Risk | Why It Matters | Preflight Check | Mitigation / Fallback |
|---|---|---|---|
| FHIR server unavailable | Every live view and analysis fails | `curl -s $FHIR_BASE_URL/metadata?_summary=true` | Retry; `FHIR_RETRIES` handles transient stalls. Record a pre-captured run as fallback. |
| Dataset-tag match | The live story needs the running gateway on the same tag as the seeded data; a restart under a different tag makes ITO vanish | `curl :8000/api/info` → `oah-demo-final`; `trend yam-ito` → `points 28` (not `0`) | **Currently correct.** If it regresses, restart the gateway so `.env` loads; never re-seed to fix it (§6.0). |
| Shared-server contamination | Public HAPI holds others' OAH resources | `_tag=…|oah-demo` total is 927; `oah-demo-final` is 908 | Always narrate the tag; never claim you own all `oah-demo*` data; use a unique tag for writes. |
| Stale overview cache | Edits/seeds may not appear for up to 60 s | `?refresh=true` returns fresh `generated_at` | F5 then `?refresh=true`; `invalidate_overview()` runs after a successful upload. |
| Browser-side live station cache | `liveStationCache` in `api.js` holds a station payload per session | Hard refresh if a just-ingested record is missing | F5 before showing "the new record". |
| Time-relative generated dates | `generate_timeseries.py` anchors to `now`; regenerating **shifts every date** and breaks the §4 numbers | Compare `/api/officer/trend` dates to the storyboard | **Do not regenerate** before recording. If you must, re-capture all quoted values. |
| Duplicate / replayed data | Idempotent `PUT` upserts the same ids; a replayed sample doesn't duplicate but can update | `_id` values are deterministic (`…-<epoch>-<i>`) | Explain upsert as a feature; avoid rapid repeated demo runs of the same sample. |
| MQTT internet access | `broker.hivemq.com` is remote and a wildcard topic sees others' traffic | Broker reachability; gateway log shows "Connected as MQTT client…" | Not needed for the ITO water/health story; skip live MQTT or pre-capture. |
| RabbitMQ readiness | Survey ingestion needs the local broker | `./run-demo.sh stack` prints `ready` | Not needed for ITO story; `INGESTION_WORKERS_ENABLED=false` removes the noise. |
| Asynchronous delivery timing | MQTT/RabbitMQ delivery + upload is not instant | Watch gateway logs for the normalized-event line | Wait for the log line, then F5; don't cut immediately. |
| Stable MQTT client ID | Session resumption needs a stable `MQTT_CLIENT_ID` | Fixed value in `.env` | Set `MQTT_CLIENT_ID` and keep it across restarts. |
| OpenAI key / model availability | Studio investigation + executive prose need it; not wired to Ollama on this branch | `echo ${OPENAI_API_KEY:+set}`; test a one-question run beforehand | **Preferred:** pre-record a good Studio run and cut it in. **Fallback:** skip the streamed narration and show the deterministic routes (`/api/officer/wards|trend|profile|persistence|offset`) plus the charts rendered from their JSON. Do not show a stuck "Investigating". |
| Studio session loss on restart | Transcript/executive 404 after restart (not used in this cut) | n/a — downloads are optional here | Skip downloads; if used, download immediately after the run. |
| Mode accidentally flipped to mock | This cut is live-only; a mock screenshot breaks the promise | Confirm the address bar shows `?mode=live` and the indicator reads `Live adapter` before every take | Never click **About this demo**'s mode link; keep a bookmark to `http://127.0.0.1:8090/?mode=live`. |
| Graph / report temptation | It is tempting to show the graph/report; both are mock | Decide in advance **not** to open the Relationships tab or Reports | State the boundary in words in the close (Scene 9); do not demonstrate simulated workflows on screen. |
| Missing observations for a station | `site_detail` 404s when a station has none under the tag | Pre-check the target station returns 200 | Only deep-link stations you verified (e.g. `site-c1-mondego` and the six Indian locations under `oah-demo-final`). |
| Nondeterministic external responses | HAPI latency varies; OpenAI output varies run to run | Two dry runs | Rehearse; keep the deterministic routes as the backbone; use "the answer will differ slightly each run" framing if needed. |
| **Accidental causal overstatement** | The entire scientific point | Re-read the caveats; check narration for banned phrases | Never say "caused", "proves a lagged effect", "identifies the discharge", "legal limit", or "real event". Use "signal worth investigating", "co-located records", "descriptive", "prototype screening reference", "confirmatory sampling". |
| **Dashboard co-location ≠ Studio co-location** | The dashboard tile never fires for ITO (no risk scores); Studio reports ITO co-located via ADD rise | Know both definitions before recording | Narrate them as **different** computations; never imply the dashboard tile corroborates the Studio finding. |
| Committed `main` README has conflict markers | Copying README lines on camera could expose `<<<<<<<` | `git show HEAD:README.md | grep -c '^<<<<<<<'` | The working tree is clean; do not switch without re-checking. |

---

## 8. Visual Enhancement Plan

A restrained set — the product interfaces stay central; graphics only label what the interface already shows.
**No slide or still may show mock fixtures, the relationship graph, a generated report, or a persona-control
screenshot.** Every graphic below annotates a live interface or a verified live API response.

1. **Opening title card** (Scene 0): "One river, two kinds of evidence" / "Yamuna at ITO Bridge — synthetic
   demonstration dataset". Thin strip of three icons: 💧 environmental measurements · 🏥 notified population
   health · ⇄ HL7 FHIR R4. Keep it under 5 s on screen.
2. **"Two evidence streams" diagram** (Scene 2, as a small inset, not full-screen): two parallel lanes —
   *Environmental (daily samples)* above, *Population health (weekly returns)* below — meeting at a single
   vertical label **"Shared FHIR Location: yam-ito"**. Emphasise the **different tick spacing** of the two
   lanes to preview the weekly-vs-daily caveat.
3. **Shared Location callout** (Scene 2): a single zoom box on the `subject = Location/yam-ito` reference in
   one water Observation and one health Observation side by side.
4. **FHIR-query highlight** (Scene 6): expand one Studio tool and draw an arrow to the exact `fhir_url`
   (`…/Observation?_profile=…&_tag=…|oah-demo-final&code=faecal_coliform&subject=Location/yam-ito…`). Blur the
   query string to a readable length; the point is "a real, auditable query ran".
5. **Threshold-basis callout** (Scene 3): side panel showing `2500 MPN/100mL` with the quoted basis
   "CPCB Primary Water Quality Criteria for Bathing Waters — maximum permissible 2500 MPN/100mL (desirable
   500)" and a footer "prototype screening reference — not a statutory limit".
6. **Timeline / river-profile zoom** (Scene 6): a close-up of the Yamuna profile's **Wazirabad → ITO** step
   (32.84× over 12 km) with the caption "largest change between these monitored stations — this narrows where
   confirmatory sampling may be useful". No arrow implying a specific discharge.
7. **Ingestion-channel convergence animation** (Scene 9): three labelled inputs MQTT / RabbitMQ / HTTP+CSV
   flowing into one pipeline bar, then out as a tagged transaction Bundle. Use the real identifiers
   (`oneaquahealth/sensors/+/+`, `ingestion.citizen_surveys`, `POST /ingest`).
8. **Selected Bundle-field highlights** (Scene 8): zoom on one generated resource showing `meta.tag`
   `{system: …/CodeSystem/dataset-tag, code: oah-demo-final}` and the transaction `request {method: PUT, url:
   Observation/<id>}` — pairing "dataset scope" with "idempotent upsert".
9. **Final loop-back visual** (Scene 9): the opening "two streams" diagram, now with a thin trace line from
   each stream back through the convergence graphic to the pipeline — closing the loop "evidence → provenance
   → evidence".
10. **Banned-from-graphics:** any correlation/regression line, any "source" pin on the river, any implication
    that a step locates a specific discharge.

---

## 9. Demo Truth Matrix

This matrix classifies every capability the earlier draft touched. Rows marked **(excluded — fails live-data
test)** are retained as an honest record of what the system does **not** do; they are **not** claims made in
the video and are **not used on camera**, because they do not make sense without mock data. The video shows
only the `LIVE` / `LIVE WITH LIMITATIONS` rows and states the boundary in words in the close.

| Demo Claim | Implementation Status | Code/Data Evidence | Safe Narration |
|---|---|---|---|
| The dashboard reads live tagged FHIR data through the gateway | LIVE WITH LIMITATIONS | `server.proxy_live()`; `web.overview()/site_detail()`; `briefing.dataset_briefing()` | "Read live from a FHIR server, scoped to a dataset tag — assuming the gateway is running on the matching tag." |
| The view is scoped by a dataset tag (`oah-demo-final`) | LIVE | `pipeline.dataset_tag()`; `bundle.tag_resources()`; `briefing._tag()` | "Everything is scoped to one dataset tag, so on a shared server we see our records." |
| ITO has environmental + health records at one Location | LIVE | 28-tag-verified series: 140 env + 16 health; `site_detail` | "Both streams cite the same FHIR Location." |
| The dashboard's `live-evidence-…` links are real FHIR `Evidence` | NOT IMPLEMENTED (they are dashboard-level refs) | `api.js liveEvidenceId()/liveEvidenceRecord()`; resolver re-fetches the station | "A dashboard-level reference derived from the station payload; the underlying record is a FHIR Observation." |
| Live overview/station co-location finding appears for ITO | NOT IMPLEMENTED (requires exceedance **and** `elevated_risk`; Indian series has no `risk_scores`) | `briefing.site_briefing()` `co_location`; verified `sites_with_co_location: []` | "The dashboard's co-location finding needs both a flag and an agency-classified elevated risk; ITO's synthetic series has no risk-score records, so it doesn't appear here." |
| The Studio finds ITO co-located | LIVE | `officer.wards()` `co_located` = exceedance AND ADD rise >15 %; verified `priority ['yam-ito']`, `add_change_pct 140.4` | "The Studio uses a different test — a screening flag plus a rise in notified cases — which is why ITO shows here." |
| Trend / change is computed, not narrated | LIVE | `officer.trend()` (verified +84.9 %) | "Computed in Python; latest 25 070 against a 2 500 criterion, ≈10×." |
| Ward ranking exists | LIVE | `officer.wards()` | "Every ward screened and ranked." |
| River profile localises a stretch | LIVE WITH LIMITATIONS | `officer.river_profile()`; verified 32.84× step | "The largest change appears between these monitored stations — it narrows where sampling may help; it does not identify a discharge." |
| Exceedance persistence | LIVE | `officer.persistence()`; verified 28/28 | "A sustained condition, not a one-off — 28 of 28 sampling days." |
| Peak offset is a **correlation**/lagged effect | NOT IMPLEMENTED (descriptive only) | `officer.peak_offset()`; `health_points 4`; caveat "not a correlation" | "A descriptive offset between two maxima — 9 days — with only four weekly points; treat as a prompt to sample, not a causal lag." |
| Screening thresholds are legal/enforcement limits | NOT IMPLEMENTED (prototype references) | `thresholds.py` docstring; `as_reference()` note | "A prototype screening reference — not a statutory limit." |
| Relationship graph is live | MOCK (**excluded — fails live-data test**) | `server.get_graph()` (fixtures); live `ApiError 501` | Not used or narrated. If asked: "the richer graph workflow is still a mock; the live gateway has no graph endpoint." |
| Station reports are live | MOCK / NOT IMPLEMENTED (**excluded — fails live-data test**) | `server.create_report()` (mock); live `createReport` 501 | Not used or narrated. If asked: "report lifecycle is prototype/mock, not live." |
| Durable run history / retry are live | NOT IMPLEMENTED (**excluded — fails live-data test**) | `api.js liveAdapter.runs` returns `[]`; `retryRun` 501 | Not used or narrated. |
| Personas enforce authorization in live mode | MOCK / SIMULATED (**excluded — fails live-data test**) | `server.require()` (mock); live `liveSession()` states intended capability only | Not used or narrated. The persona selector is visible in the browser chrome but is not discussed. |
| Ingestion sample runs through the real pipeline | LIVE | `web.ingest_demo()`; verified alert + mapping (Device1/Obs5/Loc5/Spec5) | "The same pipeline a real source uses." |
| IoT / MQTT ingestion | LIVE | `mqtt_worker.py` | "Sensors arrive over MQTT." |
| Citizen-survey / RabbitMQ ingestion | LIVE | `rabbitmq_worker.py`; queue `ingestion.citizen_surveys` | "Volunteer surveys arrive over a message queue." |
| HTTP JSON + CSV ingestion | LIVE | `app.ingest_event()/ingest_public_health_csv()`; verified CSV → 2 events | "Public-health returns arrive over HTTP, JSON or CSV." |
| Citizen surveys become `QuestionnaireResponse` | NOT IMPLEMENTED | `fhir_adapter.citizen_survey_to_fhir()` → `Observation` (`valueCodeableConcept`), `Practitioner`, `Location`, `Specimen` | "Survey answers map to OAH-profiled Observations — not QuestionnaireResponse." |
| Transaction Bundle is idempotent (upsert) | LIVE | `bundle.to_bundle()` (dedupe + `PUT`), `fhir_client.upload_bundle()` | "A transaction of PUTs, so replaying a reading updates instead of duplicating." |
| `oah-demo*` tag is a risk/analysis category | NOT IMPLEMENTED | `bundle.tag_resources()`; `fhir/resources.py` comment | "It's a dataset scope tag — not a risk class or an analytical result." |
| Dashboard auto-refreshes after ingestion | LIVE WITH LIMITATIONS | gateway `invalidate_overview()`; no browser push | "The gateway drops its cache after a successful upload, but the browser still needs a refresh." |
| Production authentication | NOT IMPLEMENTED | `HANDOVER.md`; `api.js liveSession()` | "Neither interface implements production authentication." |
| Numeric grounding verifies the answer | LIVE WITH LIMITATIONS | `grounding.check()`; verified `grounded True/False`; `not_covered` | "It checks that every number appears in the retrieved data — not that the sentence is right, and not number-free claims." |
| The synthetic data is a real event | NOT IMPLEMENTED (synthetic) | `generate_timeseries.py` docstring; `sites.json` `_comment` | "Synthetic demonstration data — the method is real, the readings are not." |
| Association implies causation | NOT IMPLEMENTED | `caveat` fields throughout | "Co-located records and a descriptive pattern — a signal worth investigating, never causation." |

---

*End of plan. Produced read-only; no application code, configuration, fixtures, or data were modified.*
