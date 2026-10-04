# Task: Build the OneAquaHealth demo-video story from the implementation on `feature/dashboard-theme-update-2`

Work only from this repository:

`/home/anindyasundar-bera/Projects/OneAquaHealth`

Work only on this Git branch:

`feature/dashboard-theme-update-2`

Expected baseline when this prompt was prepared:

`c57157d6618065b13bde00c79018ca36ac805153`

Before doing anything:

1. Run `git branch --show-current`.
2. Stop if the branch is not exactly `feature/dashboard-theme-update-2`. Do not switch branches or substitute `main`.
3. Record `git rev-parse HEAD`. If it differs from the baseline above, explicitly identify the drift and revalidate every implementation statement in this prompt against the checked-out code.
4. Confirm the worktree state.
5. Do not modify application code, configuration, fixtures, or data. This task produces a recording plan and script only.

Your job is to inspect the checked-out implementation and produce a technically accurate, code-grounded 6–8 minute demo storyboard, presenter narration, and recording runbook.

The video must feel like one investigation—not a feature tour.

The central story is:

> One river, two kinds of evidence.

The preferred implementation-grounded setting for this branch is the Indian surveillance demonstration, centered on the Yamuna at ITO Bridge (`yam-ito`), because the branch contains a 28-day cross-domain time series, FHIR-backed station evidence, and the District Surveillance Officer Studio.

The story begins with environmental measurements and notified population-health information associated with the same location. It then asks:

- What deserves attention?
- What evidence supports that assessment?
- Is the condition isolated or sustained?
- Where along the river does the change appear?
- How did the source data enter the system?
- How was it transformed into interoperable FHIR resources?
- What can—and cannot—be concluded?

Preserve this scientific boundary throughout:

> Co-location, temporal offset, and parallel trends may justify investigation. They do not prove that river conditions caused the reported health pattern.

## The repository is the source of truth

Do not rely on this prompt alone. Verify every claim in the current branch by inspecting source code, fixtures, configuration, tests, and—where safe—runtime responses.

Trace important behavior through the real implementation:

`UI → dashboard adapter/proxy → gateway route → agent/analysis code → FHIR query`

and:

`source event → validation/normalization → screening → FHIR mapping → dataset tagging → transaction Bundle → FHIR server`

Inspect at least:

- `README.md`
- `HANDOVER.md`
- `.env.example`
- `run-demo.sh`
- `docker-compose.yml`
- `dashboard/server.py`
- `dashboard/API-MAPPING.md`
- `dashboard/static/index.html`
- `dashboard/static/js/api.js`
- `dashboard/static/js/app.js`
- `dashboard/data/fixtures.json`
- `oah-ingestion/src/oah_ingestion/app.py`
- `oah-ingestion/src/oah_ingestion/web.py`
- `oah-ingestion/src/oah_ingestion/officer.py`
- `oah-ingestion/src/oah_ingestion/pipeline.py`
- `oah-ingestion/src/oah_ingestion/fhir_adapter.py`
- `oah-ingestion/src/oah_ingestion/fhir_client.py`
- `oah-ingestion/src/oah_ingestion/thresholds.py`
- `oah-ingestion/src/oah_ingestion/mqtt_worker.py`
- `oah-ingestion/src/oah_ingestion/rabbitmq_worker.py`
- `oah-agent/src/oah_agent/briefing.py`
- `oah-agent/src/oah_agent/studio.py`
- `oah-agent/src/oah_agent/grounding.py`
- `oah-agent/src/oah_agent/tools.py`
- `oah-pydantic-models/src/oah_models/fhir/`
- `oah-demo-publishers/src/oah_demo_publishers/cli.py`
- `demo/sites.json`
- `demo/generate_timeseries.py`
- `demo/timeseries/events.json`
- the supplied JSON and CSV samples
- the relevant automated tests

Search the repository rather than relying only on documentation.

## Known branch-specific implementation baseline to verify

Treat the following as leads that must be confirmed, not as permission to skip inspection.

### Applications and interfaces

This branch appears to contain three related experiences:

1. The ingestion gateway and live ingestion dashboard, normally served from `APP_PORT`, defaulting to `8000`.
2. The separate evidence dashboard, normally served from `DASHBOARD_PORT`, defaulting to `8090`, with explicit mock and live modes.
3. The District Surveillance Officer Studio at `/api/officer/panel`, linked from the live evidence dashboard as “Open Surveillance Studio.”

The evidence dashboard currently appears to expose:

- Overview
- Ingestion
- Reports
- a station workspace with Context, Evidence, and Relationships tabs
- an assistant panel
- persona and theme selectors
- a visible mock/live indicator

Verify the exact current labels before using them in the storyboard.

### Indian surveillance dataset

The repository contains a synthetic 28-day demonstration series spanning six Indian stations:

- `yam-wazirabad`
- `yam-ito`
- `yam-okhla`
- `gan-jajmau`
- `gan-assi`
- `mit-dharavi`

The generator currently describes 192 events:

- 168 water events
- 24 weekly health-surveillance events

The data is synthetic demonstration data. Station coordinates and river-distance values may be approximate. Never present it as observed CPCB, IDSP, IHIP, or state-board data.

The generator deliberately shapes an event at ITO in which:

- faecal coliform rises,
- dissolved oxygen falls,
- other water measures change,
- and a later synthetic rise appears in acute diarrhoeal disease notifications.

This pattern is a designed demonstration scenario. It is not empirical evidence of exposure, correlation, or causation.

### Surveillance Studio

Verify the implementation of these live, FHIR-backed capabilities:

- station listing
- ward prioritization
- station trends
- river longitudinal profiles
- exceedance persistence
- descriptive peak offsets
- streamed investigations
- tool and FHIR-query traces
- grounding checks for numeric claims
- downloadable investigation transcripts
- executive reports
- readings, surveillance, and FHIR Bundle exports

Likely gateway routes include:

- `GET /api/officer/stations`
- `GET /api/officer/wards`
- `GET /api/officer/trend`
- `GET /api/officer/profile`
- `GET /api/officer/persistence`
- `GET /api/officer/offset`
- `POST /api/officer/studio/run`
- `GET /api/officer/studio/report/{session_id}`
- `POST /api/officer/studio/executive`
- `GET /api/officer/export/readings.csv`
- `GET /api/officer/export/surveillance.csv`
- `GET /api/officer/export/bundle.json`
- `GET /api/officer/report/facts`

Determine which capabilities require `OPENAI_API_KEY` and which work deterministically without it.

Do not describe the Studio’s descriptive peak offset as a correlation. Verify and preserve its own caveat about the small number of weekly health observations.

### Evidence dashboard truth boundary

Verify the mock/live boundary carefully.

The expected current behavior is:

- Live overview and station views read tagged FHIR data through the ingestion gateway.
- Live findings are constructed from returned exceedances, elevated health records, and co-location state.
- IDs beginning with `live-evidence-...` are stable dashboard-level references derived from gateway station data.
- They are not stored FHIR `Evidence` resources.
- Their underlying records may be FHIR `Observation` and `Group` resources.
- Live mode does not currently have a backend graph endpoint.
- The richer Relationships graph is mock-only.
- Live mode does not provide durable ingestion-run history, run retry, or the evidence dashboard’s report lifecycle.
- The evidence dashboard’s persona controls demonstrate intended policy but do not constitute production authentication against the live gateway.

If still accurate, explain the live evidence model in plain language:

> The dashboard constructs the evidence view from station data returned by the gateway. The underlying records are stored in FHIR; the `live-evidence-...` link is a dashboard-level reference, not a separate FHIR Evidence resource.

Never present mock graph edges, mock reports, simulated role enforcement, or mock run history as live backend behavior.

### Ingestion and FHIR pipeline

Verify the three implemented source channels:

- IoT telemetry over MQTT
- citizen/community survey events through RabbitMQ
- public-health submissions over HTTP, including the CSV batch endpoint

Verify that all three reach the shared processing pipeline.

The real pipeline should be traced through:

`incoming payload`

→ `typed envelope validation and normalization`

→ `prototype threshold screening`

→ `FHIR resource mapping`

→ `meta.tag dataset scoping`

→ `transaction Bundle with deterministic PUT requests`

→ `FHIR upload`

→ `FHIR transaction response`

→ `live FHIR queries`

Do not claim that citizen surveys become `QuestionnaireResponse` resources unless the current mapper actually does so. This branch appears to map survey answers into OAH-profiled `Observation` resources, with supporting resources such as `Location`, `Specimen`, and `Practitioner`.

Confirm the actual resource types generated for each channel. Likely types include:

- `Location`
- `Specimen`
- `Observation`
- `Device`
- `Practitioner`
- `Organization`
- `Group`

Do not invent resource types.

Explain `oah-demo` accurately: it is a `meta.tag` value used to scope a prototype dataset on a shared FHIR server. It is not a risk classification, regulatory category, or analytical result.

### Screening rules

Confirm the city-specific threshold selection.

The branch appears to use:

- Indian prototype screening references for Indian cities, based on named CPCB and IS 10500 criteria.
- Separate retained European pilot conventions for measurements such as nitrate-as-N, pH, and dissolved zinc.

The software itself states that these are prototype screening references, not statutory enforcement limits. Always show the stated basis beside a threshold and preserve that limitation in narration.

### Operational limitations to verify

Explicitly investigate and classify:

- dependence on a reachable FHIR server
- the default shared HAPI FHIR sandbox
- cache behavior for overview data
- FHIR pagination and result limits
- deterministic resource IDs and replay/upsert behavior
- duplicate-data and shared-server contamination risks
- generated time-series dates being relative to execution time
- in-memory Studio sessions expiring on restart
- external MQTT connectivity
- local RabbitMQ requirements
- asynchronous delivery timing
- the need for a stable MQTT client ID for session resumption
- optional OpenAI model access
- anonymous live gateway access
- unavailable production authentication
- browser refresh requirements after ingestion
- mock/live confusion
- full Bundle JSON not being returned by the evidence dashboard’s live sample adapter
- the difference between an ingestion alert and a processing/upload failure

## Choose the strongest truthful story

Prefer a primary narrative centered on:

> Yamuna at ITO Bridge: environmental screening evidence and population-health surveillance viewed through a shared FHIR Location.

A strong candidate progression is:

1. Open the live evidence dashboard.
2. Establish that the view is scoped by the `oah-demo` dataset tag.
3. Select `yam-ito`.
4. Show environmental and health records associated with the same Location.
5. Open supporting evidence and distinguish source FHIR resources from dashboard-derived evidence links.
6. Ask whether the pattern is isolated, sustained, or visible elsewhere along the river.
7. Open Surveillance Studio and run a focused ITO or Yamuna investigation.
8. Show the real FHIR queries, computed trend/persistence/profile view, and grounding result.
9. State clearly that the scenario is synthetic and the apparent offset is descriptive only.
10. Move backward from evidence consumption to ingestion.
11. Run a supplied live sample or show one event arriving through its real channel.
12. Follow validation, screening, FHIR mapping, transaction upload, and response.
13. Briefly show how MQTT, RabbitMQ, and HTTP converge on the common pipeline.
14. Return to the live evidence view after the appropriate refresh or cache invalidation.
15. Close with interoperability, provenance, and scientific restraint.

Use the Mondego C1 material only if it provides a clearer bounded insert—for example, demonstrating the mock/live boundary or the original European pilot. Do not let it displace the stronger Indian implementation unless repository or runtime inspection shows that the Indian flow cannot be recorded reliably.

Do not force every interface into the video. Include a capability only when it advances the investigation.

## Scientific and public-health language

The narration must distinguish:

- environmental measurements,
- prototype screening flags,
- notified case counts or rates,
- cohort/location association,
- descriptive temporal offset,
- statistical association,
- and causation.

Never say or imply:

- the river caused illness,
- a downstream step identifies a specific discharge,
- a peak offset proves a lagged effect,
- a screening threshold is a legal determination,
- the synthetic data represents a real event,
- or the assistant independently establishes scientific truth.

Safe language includes:

- “a signal worth investigating”
- “co-located records”
- “a descriptive pattern”
- “screened against the prototype reference”
- “the largest change appears between these monitored stations”
- “this narrows where confirmatory sampling may be useful”
- “the available evidence does not establish attribution or causation”

## Implementation classification

Create an implementation map before designing the story. Classify each relevant capability as:

- `LIVE`
- `LIVE WITH LIMITATIONS`
- `MOCK / SIMULATED`
- `NOT IMPLEMENTED`

At minimum, classify:

- live FHIR overview and station detail
- dashboard-derived live evidence references
- relationship graph
- ingestion sample execution
- durable run history
- retry workflow
- mock report generation
- Studio investigation
- Studio charts and computed analyses
- Studio transcript export
- executive report generation
- numeric grounding
- persona authorization
- MQTT ingestion
- RabbitMQ ingestion
- HTTP JSON ingestion
- HTTP CSV ingestion
- threshold screening
- transaction Bundle generation
- FHIR upload
- dataset tagging
- automatic dashboard refresh after ingestion
- production authentication
- causal or epidemiological inference

Do not silently turn a limitation or simulation into a live feature.

## Required deliverable

Produce the following sections.

### 1. Branch and Implementation Baseline

State:

- verified branch
- inspected commit
- worktree status
- principal applications
- chosen primary demo location
- chosen dataset
- required external dependencies
- whether runtime verification was performed

Keep this concise.

### 2. Implementation Map

Use a table:

| Capability | Status | Actual Implementation | Limitation / Recording Implication | Code or Data Evidence |
|---|---|---|---|---|

Reference exact repository paths, functions, routes, fixtures, or configuration.

### 3. Narrative Decision

In a short paragraph, explain why the selected story is the strongest truthful story available on this branch.

### 4. Detailed 6–8 Minute Storyboard

Use:

| Time | Scene | Screen / Visual | Presenter Action | Narration | Technical Event | Live/Mock Status | Evidence / Code Source |
|---|---|---|---|---|---|---|---|

Every scene must specify what is physically visible:

- exact browser URL or route
- selected station
- selected tab
- button or prompt
- terminal window
- command or request
- expected response
- JSON or FHIR fields to highlight
- mode indicator
- any title card, zoom, arrow, or callout

Use actual labels and commands from the repository.

### 5. Complete Presenter Script

Write the full spoken narration.

Requirements:

- conversational
- suitable for a mixed technical and nontechnical audience
- minimal buzzwords
- technically precise
- clear transitions
- explicit mock/live distinctions
- explicit synthetic-data disclosure
- explicit association-versus-causation boundary
- consistent “one river, two kinds of evidence” theme

The script should progress naturally through:

`What is happening?`

→ `What evidence do we have?`

→ `What supports the assessment?`

→ `Is it isolated or sustained?`

→ `Where does the change appear?`

→ `Where did the records come from?`

→ `How did different inputs become FHIR data?`

→ `How does that evidence return to the user?`

### 6. Recording Runbook

Give an exact, repository-grounded sequence containing:

- environment preparation
- required `.env` values without exposing secrets
- dependency installation assumptions
- RabbitMQ startup
- ingestion gateway startup
- evidence dashboard startup
- FHIR prerequisites
- time-series generation and seeding strategy
- whether to use a controlled FHIR server instead of the shared sandbox
- whether ingestion workers should be enabled
- browser URLs
- mode query parameters
- station selection
- exact Studio prompt
- exact sample to run
- terminal arrangement
- expected logs and response states
- refresh/cache handling
- transcript/report download steps, if used
- reset and recovery steps

Use real commands from `README.md`, `run-demo.sh`, package entry points, and current configuration. Resolve any port inconsistency rather than copying commands blindly.

Avoid uploading or reseeding the shared HAPI sandbox merely to validate the storyboard. If recording requires writes, recommend an isolated FHIR server or a uniquely scoped dataset tag.

### 7. Demo Risk Checklist

Use:

| Risk | Why It Matters | Preflight Check | Mitigation / Fallback |
|---|---|---|---|

Cover at least:

- FHIR availability
- shared-server contamination
- dataset-tag mismatch
- stale overview cache
- browser-side live station caching
- time-relative generated dates
- duplicate/replayed data
- MQTT internet access
- RabbitMQ readiness
- asynchronous timing
- OpenAI key/model availability
- Studio session loss after restart
- mock/live confusion
- graph/report limitations
- missing observations
- nondeterministic external responses
- accidental causal overstatement

### 8. Visual Enhancement Plan

Recommend a restrained set of:

- opening title card
- “two evidence streams” diagram
- shared Location callout
- FHIR-query highlight
- threshold-basis callout
- timeline or river-profile zoom
- ingestion-channel convergence animation
- selected Bundle-field highlights
- final loop-back visual

Keep the product interfaces central.

### 9. Demo Truth Matrix

Finish with:

| Demo Claim | Implementation Status | Code/Data Evidence | Safe Narration |
|---|---|---|---|

Include every material claim in the presenter script.

Use only:

- `LIVE`
- `LIVE WITH LIMITATIONS`
- `MOCK`
- `NOT IMPLEMENTED`

## Quality bar

The final video must not feel like:

> Here are the features we built.

It should feel like a single, bounded investigation:

We begin with one river location.

We see two kinds of evidence associated with it.

We identify a signal that deserves attention.

We inspect the source records and screening basis.

We ask whether the pattern is sustained and where it appears along the river.

We trace one source event backward through the ingestion pipeline.

We see multiple source interfaces converge into tagged, interoperable FHIR resources.

We return to the evidence view.

We end with a precise statement of value:

> OneAquaHealth makes heterogeneous environmental and population-health evidence interoperable, visible, and traceable—while remaining honest about what that evidence cannot establish.

Do not invent commands, routes, values, resources, successful runtime behavior, or scientific conclusions. When the code and runtime disagree, report the discrepancy and build the storyboard around what can be demonstrated reliably on `feature/dashboard-theme-update-2`.
