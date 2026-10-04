# OneAquaHealth demo-video plan — "One investigation, five usable handoffs"

**Story:** one District Surveillance Officer asks one operational question about the Yamuna at ITO Bridge
(`yam-ito`); a reasoning agent chooses the evidence, the computation, and the chart that answer it; the Studio
shows its work, checks the figures in its conclusion, and turns the *same* investigation into five usable
handoffs — an audit transcript, an executive situation report, an environmental readings CSV, a
health-surveillance CSV, and a tagged FHIR R4 collection Bundle.

**Audience:** mixed technical / non-technical (district health officers, environmental agencies, hackathon and
policy reviewers). **Target runtime:** 3:00–5:00, targeting **≈4:30**. **Hard ceiling: 5:00.**

> **This document is a recording plan and script only.** No application code, configuration, fixtures, source
> data, or existing media were modified to produce it. Every capability was classified by reading the
> checked-out source and tests and, where safe, by issuing **read-only** requests to the services already
> running on this machine. No data was uploaded, reseeded, ingested, or mutated.

> **Governing rule — the live-data test.** A capability appears on camera **only if it still makes sense when
> every record comes from the live FHIR server**. Nothing that exists only in the dashboard's mock fixtures is
> exercised on screen: no `?mode=mock`, no relationship graph, no mock report lifecycle, no mock run
> history/retry, no simulated persona authorization. Those features are still *classified* as `MOCK /
> SIMULATED` or `NOT IMPLEMENTED` in §9.3 and §9.11 — the classification is part of the honest record — but they
> are never opened on camera. Everything the camera shows is backed by live, tagged FHIR data.

> **Governed by the previous task's authority order.** Current checked-out source and tests outrank runtime
> responses, which outrank the recent audit (`surveillance-studio-capability-and-story-audit.md`), which outrank
> the superseded plan, narration and shot-list, which outrank general documentation. The audit and the older
> plans were treated as leads and re-verified, not as instructions.

---

## 9.1 Verified baseline

| Item | Verified value |
|---|---|
| Branch checked out | `feature/data-fix-and-video-story` |
| HEAD commit | `a2d377b476d0d59b86d3cad52cc900ae7e80dd13` (merge of PR #16; also `origin/main`) |
| Inspection date | 2026-10-04 (UTC); revalidated the same day with both services still up |
| Worktree state | **Dirty — 246 entries, all preserved.** Modified (tracked): `dashboard/static/js/studio.js`, `dashboard/static/studio.css`, `oneaquahealth-demo-video-plan.md`, `oneaquahealth-video-generation-prompt.md`, `oneaquahealth-demo-video-prompt.md`. Staged/untracked (production assets only): `surveillance-studio-capability-and-story-audit.md`, `surveillance-studio-story-investigation-prompt.md`, `video/**`, `vidkit/**` (incl. `vidkit/docs/`, `vidkit/tests/test_mcp.py`, `vidkit/vidkit/{mcp_server,reports}.py`), `.vscode/`, `.mcp.json`. **None touched by this task.** |
| Runtime checks | **Read-only.** `GET` on gateway, dashboard, FHIR, and the officer/Studio/export routes, plus one streamed `POST /api/officer/studio/run` (read-only — it neither writes to FHIR nor persists beyond the in-memory session). No write to FHIR was issued while writing this plan. |
| Ingestion gateway | `http://127.0.0.1:8000` — `/health` → `{"status":"ok"}` |
| Evidence dashboard | `http://127.0.0.1:8090` — `/health` → `{"status":"ok", ...}` |
| FHIR base URL | `https://hapi.fhir.org/baseR4` (shared public HAPI sandbox) |
| Dataset tag | `oah-demo-final` (verified via `/api/info` → `fhir.dataset_tag`) |
| Story station | `yam-ito` — "Yamuna at ITO Bridge", city `delhi`, district Central Delhi, reach "Yamuna — mid-city, downstream of Najgarh drain", `flow_km=12` |
| Time window | Windows are **per-analysis and must be stated**: trend/wards/persistence 28 days; river profile **14 days by default** (the source of the numbers drift noted in §9.4); offset 28 days; readings CSV 28 days; health CSV 90 days |
| Overview | `site_count: 6`; `sites_with_exceedances`: `[yam-ito, yam-okhla, gan-jajmau, gan-assi, mit-dharavi]`; `sites_with_co_location: []`; `yam-ito` briefing: 140 environmental + 16 health readings |
| Model availability (observed, no secrets) | **The running gateway has a working model credential.** Verified two ways, read-only: (a) the gateway process listening on `:8000` has a non-empty `OPENAI_API_KEY` in its environment; (b) a live streamed `POST /api/officer/studio/run` completed, emitting `start → thinking → 3× (tool_start / tool_done) → render(trend) → answer → done`. The credential's **value** is not recorded here. The interactive shell does not see it; the running gateway does. (An earlier `video/shot-list.md` claim that the key is "not set" reflected the shell, not the service, and is stale — see §9.4.3.) |
| Model code path | `oah-agent/src/oah_agent/studio.py` `_client()` imports the **OpenAI SDK** directly and requires `OPENAI_API_KEY`. There is **no `llm.py` provider abstraction** on this checkout, so `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in `.env` are **dead configuration** — setting them does not route the Studio to a local model. |
| Principal files used as evidence | `oah-agent/src/oah_agent/{studio,tools,grounding,briefing}.py`; `oah-ingestion/src/oah_ingestion/{officer,web,pipeline,thresholds,fhir_client}.py`; `oah-pydantic-models/src/oah_models/fhir/bundle.py`; `dashboard/server.py`; `dashboard/static/js/{api,app,studio,studio-api,studio-charts}.js`; `dashboard/static/index.html`; `demo/sites.json`; `dashboard/tests/{test_gateway_integration,test_studio_proxy,test_server}.py`; `oah-agent/tests/{test_studio,test_grounding}.py`. |

**Runtime availability note for production.** The services were already running with `oah-demo-final` and a live
model credential during this inspection. If production finds them down or the tag drifted, restart the launcher
(`python run.py`, which loads the root `.env`) rather than re-seeding; never re-seed to fix a tag mismatch
(see §9.9, §9.8).

---

## 9.2 Executive narrative decision

**Audience promise.** *Follow one real surveillance question from the moment an officer asks it to the moment it
becomes five different handoffs — and see exactly how far the evidence lets anyone go.*

**Why one investigation, not a feature tour.** The repository's most distinctive capability is not a screen; it
is a *loop*: a question → typed FHIR retrieval → Python-computed analysis → a model-chosen chart → a
numerically grounded conclusion → reusable artifacts. A feature tour would show the overview, then a matrix,
then an export button, and would prove nothing about how any of it connects. A single bounded investigation
lets every on-screen artifact be *the output of the run the viewer just watched*, which is the whole point.

**Why the handoff is the payoff.** The older cut ended on a convergence graphic and a disclaimer. That is a
provenance story. The stronger story is operational: the finding is not the deliverable — the *handoff* is. The
same transcript becomes four artifacts addressed to four recipients, plus one interoperable export:

| Artifact | Recipient | Their job | One line |
|---|---|---|---|
| Investigation transcript (HTML) | Auditor / incident record | Verify *how* the conclusion was reached | **"How we reached it."** |
| Executive situation report (print-ready HTML) | District Surveillance Officer / Chief Medical Officer | Decide what to do today | **"What leaders need to decide."** |
| Environmental readings CSV | Analyst | Work the measurements, screening basis, exceedances | **"What analysts can reuse."** |
| Health-surveillance CSV | Analyst | Work cases, denominators, rates, baselines | **"What analysts can reuse."** |
| Tagged FHIR R4 collection Bundle | ABDM-aligned / FHIR-capable system | Attach machine-readable evidence, no retyping | **"What systems can reuse."** |

The narrative must stay a single bounded investigation. It must **not** become a download-button tour: the
storyboard opens the transcript, the report, both CSV headers, and the key Bundle fields on screen, and it names
the recipient and the job for each.

**What moved to the appendix and why.** The full ingestion/provenance walkthrough (MQTT, RabbitMQ, HTTP JSON,
HTTP CSV, mapping, transaction Bundle, upload, tagging), the comparison charts (matrix/ranking/scatter), the
deterministic report facts, and the model-free endpoint verification are all valuable but they are not the
handoff. They are demoted to a **separate 60–90 s appendix** so the main cut can spend its largest block on the
real Studio run and the artifacts, rather than on terminal output. The main cut keeps a **concise ~15 s
provenance bridge** so the records' origin is still on screen.

**Emphasis budget for the main cut** (proves the balance, §9.5 total is below 5:00):

- ~24% live context and evidence boundary (§9.5 Scenes 0–3 = 65 s of 270 s).
- ~33% real streamed Studio investigation, tool choice, charts, grounding (Scenes 4–7 = 89 s).
- ~36% transcript, executive report, CSVs, FHIR Bundle (Scenes 8–11 = 97 s).
- ~7% provenance bridge and close (Scene 12 = 19 s; the bridge is deliberately minimal).

---

## 9.3 Implementation and truth map

Classification uses exactly one of: `LIVE — deterministic` · `LIVE — model required` · `LIVE — session-dependent` ·
`LIVE WITH LIMITATIONS` · `MOCK / SIMULATED` · `NOT IMPLEMENTED` · `UNVERIFIED`.

| Capability | Classification | User value | Actual implementation path | Dependencies | Limitations | Placement | Evidence |
|---|---|---|---|---|---|---|---|
| Live overview | `LIVE WITH LIMITATIONS` | Dataset scope at a glance | `/api/live/overview` → `server.live_overview()` → gateway `/api/overview` → `briefing.dataset_briefing()`; 60 s cache | Reachable FHIR + correct tag | Cache; no push refresh; co-location list is empty for India | Main (Scene 1) | `web.overview()`, `_overview_cache`; `api.js liveAdapter.summary`; live: `site_count 6` |
| Live station detail | `LIVE WITH LIMITATIONS` | One station's evidence | `/api/live/sites/{id}` → `/api/sites/{id}` → `site_briefing(include_observations=True)` | Same | 404 when no observations for the tag | Main (Scenes 2–3) | `web.site_detail()`; live `yam-ito` → 200, 140 env + 16 health |
| Dashboard-derived `live-evidence-*` references | `LIVE WITH LIMITATIONS` | Links a finding to its record | `api.js liveFindings()/liveEvidenceId()/liveEvidence()` derived from the station payload; resolver re-fetches station | Same | These are **dashboard-level references**, not stored FHIR `Evidence`; underlying record *is* a FHIR `Observation` | Main (Scene 3) | `api.js liveEvidenceRecord()`, `liveStationCache` |
| Dashboard "co-located sites" finding for ITO | `NOT IMPLEMENTED` | — | needs exceedance **and** `elevated_risk`; Indian series has no risk scores | — | Never fires for ITO; must not be implied | Main (stated, never shown firing) | live `sites_with_co_location: []`; `briefing.site_briefing()` |
| `get_thresholds(city)` | `LIVE — deterministic` | Stops the model quoting a "safe level" from memory | `tools.get_thresholds()` → `thresholds.as_reference()` | None (pure Python) | Prototype screening references | Main (Scene 5, first tool) | `tools.py`; `thresholds.py` docstrings |
| `list_sites()` | `LIVE — deterministic` | Resolves "this station" | `tools.list_sites()` → FHIR `Location?_tag=…` | FHIR + tag | `_count=200` | Exclude (no screen time) | `tools.py` |
| `search_observations(kind, indicator, site_id, since/until, limit)` | `LIVE — deterministic` | Retrieval primitive behind every number | `tools.search_observations()` typed profile + `_tag` scope | FHIR + tag | Client-side value filter; cap 200 | Appendix | `tools.py` |
| `get_site_profile(site_id)` | `LIVE — deterministic` | One Health join (env + health + cohorts) | `tools.get_site_profile()` (3 searches) | FHIR + tag | No temporal alignment | Main (Scene 5, streamed tool chip) | `tools.py`; live run called it first |
| `get_cohort(group_id)` | `LIVE — deterministic` | Explains *who* a health measure describes | `tools.get_cohort()` → FHIR `Group` | FHIR + tag | Returns `error` dict if absent | Exclude | `tools.py` |
| Typed-tool safety property (model never writes a FHIR URL) | `LIVE — deterministic` (design property) | Prevents plausible-but-empty queries | `tools.py` module docstring; `search_url()`; `studio.SYSTEM` forbids URLs | — | — | Main (narrated, Scene 5) | `tools.py`; `studio.py SYSTEM` |
| `trend(site, indicator, days)` + period change | `LIVE — deterministic` | What moved, by how much | `officer.trend()`; **mean of the most recent `days//2` against the `days//2` before** | FHIR + tag | Change is mean-vs-mean of window halves, not last-7-days | Main (Scene 5 chart) | `officer.trend()`; live +84.9% |
| `wards(days)` rank + `co_located` | `LIVE — deterministic` | Tuesday-morning triage order | `officer.wards()`; 60 s `_WARDS_CACHE` | FHIR + tag | `co_located` = exceedance **and** ADD rise >15% (different test from the dashboard). The Studio's `rank_wards` also returns an `fhir_urls` value that **hard-codes the `|oah-demo` suffix** regardless of `OAH_DATASET_TAG` — do not read it as proof of the live tag | Main (Scene 5, tool) | `officer.wards()`; live priority `['yam-ito']`; `studio.rank_wards()` |
| `river_profile(river, indicator, days)` + largest step | `LIVE — deterministic` | Localises the stretch a load enters on | `officer.river_profile()`; `sites.flow_km` order | FHIR + tag | **`days` default = 14**; result is window-sensitive; step does not identify a discharge | Main (Scene 5 chart, Scene 7 caveat) | `officer.river_profile()`; see §9.4 for both windows |
| `persistence(days, indicator)` | `LIVE — deterministic` | One-off vs sustained | `officer.persistence()`; per-date dedupe | FHIR + tag | Run = consecutive **sampling** days | Main (Scene 5 chart) | `officer.persistence()`; live 28/28 |
| `peak_offset(site, indicator, days)` | `LIVE — deterministic` | Honest temporal comparison | `officer.peak_offset()` | FHIR + tag; `days ≥ 14` | Descriptive; `health_points` usually 4; **not** a correlation | Main (Scene 7) | `officer.peak_offset()`; live +9 d / 4 points |
| `report_facts(days)` | `LIVE — deterministic` | Ground truth for the report, no model | `officer._report_facts()` | FHIR + tag | — | Appendix | `officer.py` |
| Streamed Studio investigation (SSE) | `LIVE — model required` | Watch the reasoning, not a spinner | `studio.run()` → `officer.studio_run()` → `POST /api/officer/studio/run`; dashboard `live_studio_run()` | **Model credential** | `MAX_ROUNDS=10`; nondeterministic tool choice | **Main — centrepiece (Scenes 4–6)** | `studio.py run()`; live run completed |
| Studio persona gate (Analyst required) | `LIVE — session-dependent` | The Studio is offered only to the Analyst persona | `studio.js initStudio()` — `allowed()` = `apiMode === "live" && state.role === "analyst"`; the **Surveillance** nav item is hidden unless `state.session.capabilities.canQueryAssistant`; live support requires the Analyst permission `assistant.ask` **and** `LIVE_CAPABILITY_SUPPORT` | Analyst persona chosen in the top-bar `#persona-selector` | **The default persona is not Analyst**, so the composer stays disabled until Analyst is selected. Personas are a demo policy control, not authentication | Main (Scenes 1 & 4 — must select Analyst) | `studio.js allowed()`; `api.js ROLES`/`capabilitySnapshot()`; `index.html` persona control |
| Model chooses tools **and chart form** | `LIVE — model required` | "Which chart answers this" is a reasoning step | `STUDIO_IMPLEMENTATIONS` / `STUDIO_SCHEMAS`; `SYSTEM` | Model credential | Prompt prefers 2–3 views | Main (Scene 5) | `studio.py` |
| Argument repair (`window_days→days`, `station→site_id`, drop unknown) | `LIVE — deterministic` | A guessed arg costs a retry, never the call | `studio._clean()`, `_ALIASES` | — | — | Appendix | `test_studio.py ArgumentCleaningTests` |
| In-memory sessions | `LIVE — session-dependent` | Lets the follow-on downloads resolve | `studio.SESSIONS` (dict) | — | **Lost on process restart**; no TTL; not shared across workers | Main (stated, Scenes 8–11) | `studio.py SESSIONS`; live 404 after restart |
| Dashboard injects station context | `LIVE — deterministic` | Makes "current station" precise | `dashboard/server.live_studio_run()` appends `Dashboard context: investigate station <id>` | — | Context injection, not a hard filter | Appendix | `server.py live_studio_run()` |
| 7 render types: `stats, matrix, ranking, trend, scatter, profile, persistence` | `LIVE — deterministic` | Each answers a different question | `studio-charts.js createChartRenderer()` | Browser only | Tool returns a spec; browser draws it | Main (2–3 forms), appendix (rest) | `studio-charts.js` |
| Two aligned panels, never a dual y-axis | `LIVE — deterministic` | Coliform (10⁴) and cases (10¹) stay honest | `drawTrend()` | — | — | Main (Scene 5) | `studio-charts.js drawTrend()` |
| Numeric grounding verdict | `LIVE — deterministic` | "Did it make this up?" is checked, not asked | `grounding.check()`; verdict attached to the `answer` event | — | **Checks numeric literals only**: a grounded figure can sit in a wrong sentence; number-free claims unchecked. Reports `figures_checked`, `source_figure_count`, `unsupported_figures`, `not_covered` | Main (Scene 6) | `grounding.py`; `test_grounding.py`; live run grounded (all-checked pass) |
| Grounding sources include chart specs and query args | `LIVE — deterministic` | Charts are evidence; "the past 28 days" is a fact | `studio.run()` appends `result`, `args`, `render` to sources | — | Args are facts, not a licence to quote a filter as a threshold | Main (stated, Scene 6) | `studio.py`; `test_studio.py GroundingSourceTests` |
| Visible tool arguments + FHIR evidence links | `LIVE — deterministic` | Any claim can be re-run by hand | `tool_done` carries `urls` + `arguments`; `studio.js` renders an expandable `<details>` | — | — | **Main (Scene 5 — expand one)** | `studio.js`; `officer.studio_report()` "Queries run" |
| Investigation transcript (HTML) | `LIVE — session-dependent` | Auditability: *how* it was reached | `officer.studio_report(session)`; proxy `/api/live/studio/transcript/{s}` | Valid session | 404 after restart; self-contained HTML, **not** PDF | **Main (Scene 8)** | `officer.studio_report()`; live 15 KB, `Content-Disposition: attachment` |
| Executive situation report (HTML, print-styled) | `LIVE — model required` | Decision-makers | `officer.studio_executive()`; `EXEC_PROMPT` JSON-mode call; proxy `POST /api/live/studio/executive` | Model credential + valid session | **Print-ready HTML with browser Save-as-PDF — not a native PDF**; the gateway returns `HTMLResponse` with **no `Content-Disposition`**, and `studio.js executive()` fetches the body and **downloads it as `surveillance-report-<session>.html`** (it does *not* open a tab); re-grounds the report text | **Main (Scene 9)** | `officer.studio_executive()`; `studio.js executive()`; `@page`, `window.print()` |
| Executive report embeds the run's actual chart SVGs | `LIVE — session-dependent` | Report carries the charts the analyst chose | `studio.js executive()` collects `.viz` SVGs → `figures[]`; capped at 30 | SVGs in the live DOM | — | Main (Scene 9) | `studio.js executive()`; `server.live_studio_executive()` |
| Deterministic report facts | `LIVE — deterministic` | Model writes prose over facts it cannot alter | `officer._report_facts()` | FHIR + tag | — | Appendix | `officer.py` |
| Environmental readings CSV | `LIVE — deterministic` | Readings + criterion + basis + Observation id | `officer.export_readings()`; proxy `/api/live/studio/export/readings` | FHIR + tag | Station-scoped if `site_id`; else all | **Main (Scene 10)** | `officer.export_readings()`; live 141 rows |
| Health-surveillance CSV | `LIVE — deterministic` | Cases, denominators, rates, baselines | `officer.export_surveillance()`; proxy drops `site_id` | FHIR + tag | **District-wide only** | **Main (Scene 10)** | `officer.export_surveillance()`; live 97 rows |
| Tagged FHIR R4 collection Bundle | `LIVE — deterministic` | Machine-readable station evidence | `officer.export_bundle()`; proxy `/api/live/studio/export/fhir` | FHIR + tag + **`site_id` required** | `type: collection`; `meta.tag` = dataset tag; single station; not a transaction and creates no `Evidence` resource | **Main (Scene 11)** | `officer.export_bundle()`; live 156 entries |
| Ingestion sample execution | `LIVE WITH LIMITATIONS` | Proves records have a traceable origin | `web.ingest_demo(key)` through the real `pipeline.process()` | FHIR (writes unless disabled) | Response shows `observations[:4]`; `upload.resources` counts built entries (Location deduped) | Appendix (bridge only) | `web.py ingest_demo()` |
| MQTT ingestion | `LIVE WITH LIMITATIONS` | Sensor transport | `mqtt_worker.create_mqtt_client()` (MQTT v5, QoS 1, manual ack) → `process()` | Public broker reachability | Shared public broker; ack withheld on upload failure | Appendix | `mqtt_worker.py` |
| RabbitMQ ingestion | `LIVE WITH LIMITATIONS` | Survey transport | `rabbitmq_worker.consume_citizen_surveys()` on `ingestion.citizen_surveys` | Local broker | Acks only after pipeline success; nack/requeue | Appendix | `rabbitmq_worker.py` |
| HTTP JSON ingestion | `LIVE` | Public-health transport | `POST /ingest` → 202/502/500 | Writes to FHIR | Anonymous | Appendix | `app.py ingest_event()` |
| HTTP CSV ingestion | `LIVE` | Batch public-health transport | `POST /ingest/public-health/csv` groups rows by `event_id` | Writes to FHIR | Validated before processing | Appendix | `app.py`; `csv_ingestion.py` |
| Threshold screening | `LIVE — deterministic` | Screening before conversion | `thresholds.evaluate()` city-selected; `alerts.assess()` | None | **Prototype screening references, not statutory limits** | Main (Scene 3 basis, Scene 7 caveat) | `thresholds.py`; `alerts.py` |
| FHIR mapping | `LIVE — deterministic` | Envelope → OAH-profiled resources | `fhir_adapter.envelope_to_fhir()` | — | — | Appendix | `fhir_adapter.py` |
| Transaction Bundle generation | `LIVE — deterministic` | Idempotent upsert | `bundle.to_bundle()` dedupe + `PUT <Type>/<id>` entries | — | `fullUrl` only when `base_url` given | Appendix | `bundle.py`; `test_fhir_mappers.py` |
| FHIR upload | `LIVE` | Writes tagged records | `fhir_client.upload_bundle()` POSTs to `FHIR_BASE_URL`; `FHIR_RETRIES` | Shared sandbox | No HTTP-level retry beyond broker redelivery | Appendix | `fhir_client.py` |
| Dataset tagging | `LIVE` | Scopes every query on a shared server | `bundle.tag_resources()` stamps `meta.tag` system `…/dataset-tag`, code `OAH_DATASET_TAG` | — | **Dataset scope tag only — not a risk class**; changing it does not retag stored data | Main (Scene 1, Scene 11) | `bundle.tag_resources()` |
| Relationship graph | `MOCK / SIMULATED` | — | `server.get_graph()` reads fixtures; live adapter throws 501 | — | Live gateway has no graph route | **Exclude** (never opened) | `server.py`; `api.js liveAdapter.graph` |
| Mock report lifecycle + downloads | `MOCK / SIMULATED` | — | `server.create_report()`/`report_html()`; live `createReport` 501 | — | **Separate** from the Studio's live report/transcript | **Exclude** (stated) | `server.py`; `api.js liveAdapter.reports` |
| Durable run history / retry | `NOT IMPLEMENTED` | — | `api.js liveAdapter.runs` → `[]`; `retryRun` 501 | — | — | Exclude | `api.js` |
| Persona authorization | `MOCK / SIMULATED` | — | `server.require()` enforces in mock; live `liveSession()` expresses intended capability only | — | Not production auth | Exclude (stated) | `server.py`; `api.js` |
| Production authentication | `NOT IMPLEMENTED` | — | — | — | Gateway anonymous | Exclude (stated) | `README.md`; `api.js liveSession()` |
| Causal / epidemiological inference | `NOT IMPLEMENTED` | — | Deliberately absent; `caveat` fields throughout | — | Peak offset is descriptive only | Main (stated, Scene 7 & 12) | `briefing.py`/`alerts.py`/`officer.peak_offset()` caveats |

---

## 9.4 Verified values and artifact contracts

Every value below was re-derived **read-only** from the running gateway on **2026-10-04 ~11:24–11:26 UTC**. A
value is **safe to hard-code in narration only if this table says so and production re-checks it immediately
before recording**; transient row counts and window-sensitive calculations must always be refreshed.

### 9.4.1 Analysis values

| Quantity | Route & exact parameters | Result (this retrieval) | Safe to hard-code? |
|---|---|---|---|
| ITO coliform latest | `GET /api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28` | `latest 25070.0 MPN/100mL`, threshold `2500.0`, factor `10.03` | Yes, but refresh before recording |
| ITO coliform change | same | recent mean `37775.21` vs prior `20433.36` → `+84.9%`; basis **"mean of the most recent 14 days against the 14 before"** | Yes; do **not** call it "last-7-days" |
| Ward priority | `GET /api/officer/wards?days=28` | `priority ['yam-ito']`; ITO ADD `+140.4%`, `co_located true`; Okhla `−6.4%`; Dharavi `−10.3%` | Yes, but refresh |
| River profile (default window) | `GET /api/officer/profile?river=Yamuna&indicator=faecal_coliform` (**`days=14` default**) | Wazirabad `886.93` → ITO `37775.21` (15.11×) → Okhla `32294.29` (12.92×); largest step **`42.59× / 12 km`** | **No — window-sensitive; state the window** |
| River profile (28-day window) | `…&days=28` | Wazirabad `886.14` → ITO `29104.29` (11.64×) → Okhla `33126.75` (13.25×); largest step **`32.84× / 12 km`** | **No — window-sensitive; state the window** |
| Persistence | `GET /api/officer/persistence?days=28&indicator=faecal_coliform` | `yam-ito 28/28`, longest run `28` | Yes, but refresh |
| Descriptive peak offset | `GET /api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28` | water peak `2026-09-24` (`84802`), health peak `2026-10-03` (`69.42`/100k) → `offset_days 9`, `health_points 4` | Yes; always quote the caveat |
| Ingested sample alert (appendix) | `POST /api/ingest-demo/iot` | `[HIGH] yam-ito (delhi)`: coliform `84802` (33.92×), BOD `16.8`, DO `0.9`, NH₃-N `5.6`; built counts `Device 1, Observation 5, Location 5, Specimen 5` | Yes; **write — see §9.8** |

**Value-drift explanation (must be recorded, not hidden).** The recent audit reported a river-profile
discrepancy against the older plan: live `42.59×` vs plan `32.84×`. This was **investigated and fully explained
by the `days` window**: the endpoint's default is `days=14`, which yields `42.59×`, and `days=28` yields
`32.84×`. The seeded series was not reseeded. **Consequence for production: every river-profile number on
screen must name its window ("over the last fourteen days" / "over the last twenty-eight days"), and no older
plan's table may be reused.** The same discipline applies to trend (28 d), persistence (28 d), offset (28 d),
readings CSV (28 d) and health CSV (90 d).

### 9.4.2 Artifact contracts

| Artifact | Route | MIME type | Filename / disposition | Key columns / fields | Scope | Session behaviour |
|---|---|---|---|---|---|---|
| Investigation transcript | `GET /api/live/studio/transcript/{session}` → gateway `GET /api/officer/studio/report/{session}` | `text/html; charset=utf-8` | `attachment; filename="investigation-<session>.html"` | Request; each `thinking`; each tool step with `arguments`, `summary`, **"Queries run"** URLs and a render note; conclusion; grounding chip + `not_covered`; footer | One investigation | **404 after gateway restart** |
| Executive situation report | `POST /api/live/studio/executive {session, figures[]}` → gateway `POST /api/officer/studio/executive` | `text/html; charset=utf-8` | **The gateway sends no `Content-Disposition`.** The dashboard's `studio.js executive()` fetches the body and **downloads it as `surveillance-report-<session>.html`** (a blob download — it does *not* open a tab) | Sections: Situation, Key findings (table), Assessment, Figures (embedded SVGs), Recommended action, Limitations, Verification chip, signature lines, appendix of evidence queries; `@page A4`; `window.print()` | One investigation | 404 without a valid session; 502 on model error |
| Readings CSV | `GET /api/live/studio/export/readings?days=28&site_id=yam-ito` | `text/csv; charset=utf-8` | `attachment; filename="oah-readings-yam-ito-28d.csv"` | `date, site_id, station, district, indicator, value, unit, threshold, exceedance_factor, basis, observation_id` (141 lines incl. header) | One station (or all when `site_id` omitted) | None |
| Health-surveillance CSV | `GET /api/live/studio/export/surveillance?days=90` | `text/csv; charset=utf-8` | `attachment; filename="oah-surveillance-90d.csv"` | `date, site_id, station, district, cohort, condition, cases, population_at_risk, rate_per_100k, baseline_per_100k, observation_id` (97 lines) | **District-wide** — the proxy intentionally does not forward `site_id` | None |
| Tagged FHIR Bundle | `GET /api/live/studio/export/fhir?days=28&site_id=yam-ito` | `application/fhir+json` | `attachment; filename="oah-evidence-yam-ito-28d.json"` | `resourceType: Bundle`, `type: collection`, `total: <n>` (156 at an earlier retrieval — **count is window/tag-sensitive; refresh and do not freeze it**), `meta.tag [{system: …/CodeSystem/dataset-tag, code: oah-demo-final}]`, all entries `Observation`, `fullUrl: <base>/Observation/<id>`; **422 without `site_id`** | One station | None |

All three exports are **deterministic** (Python over tagged FHIR reads). The executive report's prose is
**model-produced** and will differ between runs; its figures are re-grounded against the transcript the model was
given.

### 9.4.3 Revalidation record — stale-document corrections

Every claim above was re-derived **read-only** against the running services on 2026-10-04, and the current
checked-out source was read directly. Where a superseded document disagrees, the correction is:

| Stale claim (source) | Verified reality (current code + runtime) | Where it matters |
|---|---|---|
| "`OPENAI_API_KEY` is **not set**, so Scenes 5–7 use the deterministic fallback" (`video/shot-list.md`, `video/produce/README.md`, `vidkit/examples/oneaquahealth/README.md`) | **The running gateway has a non-empty `OPENAI_API_KEY`; a live streamed `studio/run` completed** (`start → thinking → 3 tool calls → render → answer → done`). The shell lacks the key; the service has it | The main cut **must** record the real streamed run; terminal output is not a substitute |
| "`LLM_PROVIDER=ollama` routes the Studio to a local model" (implied by `.env`'s Ollama block) | `studio._client()` imports the **OpenAI SDK** directly and there is **no `oah_agent/llm.py`** — the Ollama/`OLLAMA_*` settings are **dead configuration** for the Studio | Do not record an expectation of a local model; do not "fix" `.env` (out of scope) |
| "the executive report opens in a tab" (earlier plan/prompt wording) | Gateway returns `HTMLResponse` with **no `Content-Disposition`**; `studio.js executive()` **downloads** `surveillance-report-<session>.html` via a blob | Scene 9 must open the report from the **downloads bar**, then Save-as-PDF |
| "the Studio needs only live mode" | The composer is gated on the **Analyst persona** (`studio.js allowed()`), and the nav item on `canQueryAssistant` | Scenes 1 and 4 must **select Analyst** before filming |
| river-profile "32.84×" vs "42.59×" (older plan vs audit) | **Both are correct for different `days`**: default `days=14` → `42.59× / 12 km`; `days=28` → `32.84× / 12 km`. Not a re-seed | Every profile figure on screen must **name its window** |
| `rank_wards` evidence link shows the live tag | `studio.rank_wards()` hard-codes `…?_tag=…|oah-demo` in its `fhir_urls` | Never present that string as the live dataset tag; use the overview/transcript scope line instead |

---

## 9.5 Detailed main-cut storyboard

Assumed state: gateway on `oah-demo-final` with live model access; dashboard at
`http://127.0.0.1:8090/?mode=live`; station **Yamuna at ITO Bridge**. Two terminals only where noted (B =
shell for the CSV/Bundle open, or the provenance bridge). Every scene names its exact URL, scope, control,
expected state, the field to highlight, its dependency class, and whether a fallback is allowed in the main cut.

**Total: 4:30 (270 s).** Below the 5:00 ceiling.

| Time | Scene | Screen / visual | Presenter action | Narration purpose | Technical event | Classification | Evidence | Fallback allowed? |
|---|---|---|---|---|---|---|---|---|
| 0:00–0:08 (8 s) | 0 Title | Title card: "One investigation, five usable handoffs"; subtitle "Yamuna at ITO Bridge — synthetic demonstration dataset" | Hold on card | Promise: a question becomes five handoffs | None | Card | §9.10 | n/a |
| 0:08–0:22 (14 s) | 1 Scope | `http://127.0.0.1:8090/?mode=live`; mode indicator **Live adapter**; **select the Analyst persona** in the top-bar persona control; left nav **Overview / Ingestion / Surveillance** (Surveillance appears only for Analyst); scope line "Dataset tag oah-demo-final on https://hapi.fhir.org/baseR4" | Point at mode indicator, then the persona control, then the scope line; select station Yamuna at ITO Bridge | One investigation, one place, one tag — and the Studio requires the Analyst persona | `GET /api/live/overview` → `dataset_briefing()`; `studio.js allowed()` gate | LIVE WITH LIMITATIONS | §9.3; live `site_count 6` | No (live only) |
| 0:22–0:45 (23 s) | 2 Two kinds of evidence | Station **Context** tab: environmental readings (faecal coliform, BOD, DO) above; health measures (acute diarrhoeal disease) below; both `subject = Location/yam-ito`; different cadences (daily vs weekly) | Scroll; highlight one coliform row and one ADD row | The two evidence streams are at one FHIR Location on different clocks | `GET /api/live/sites/yam-ito` → `site_briefing(include_observations=True)` | LIVE WITH LIMITATIONS | live 140 env + 16 health | No |
| 0:45–1:05 (20 s) | 3 What deserves attention | **Evidence** tab; open one finding drawer → `FHIR_OBSERVATION` (the reading) + `THRESHOLD_RULE` (CPCB basis, 2500 MPN/100mL) + `live-evidence-…-yam-ito` id | Open drawer; point at the two record types and the basis | Screening flag + quoted basis; the reference is dashboard-level, the record is real | `api.js liveFindings()/liveEvidence()`; `thresholds.INDIAN_THRESHOLDS` | LIVE WITH LIMITATIONS | §9.4; live exceedance 10.03× | No |
| 1:05–1:30 (25 s) | 4 Ask | Surveillance Studio: **Analyst persona selected**; scope **Current station**; type `Investigate the Yamuna at ITO Bridge over the last month.`; press **Investigate**; "Starting investigation…" appears | Type the prompt aloud; press Investigate | The officer asks one operational question; the agent, not the human, chooses the path | `POST /api/live/studio/run` → `live_studio_run()` (appends station context) → `studio.run()` SSE | **LIVE — model required** | `studio.js run()`; live run completed | **Yes but labelled** (deterministic routes as a clearly-labelled alternate; never a fake agent) |
| 1:30–2:30 (60 s) | 5 Agent at work | The real streamed run: reasoning lines; tool chips; **expand exactly one** to reveal its `arguments` and FHIR query URL; **two or three** model-chosen charts render (two-panel trend; river profile Wazirabad→ITO→Okhla; persistence strip). **Revalidate live:** a probe run on 2026-10-04 emitted 3 tools and 1 render (a trend) — a valid run, but the cut needs **≥2 chart forms**, so **warm/re-run the same question** until two forms appear (see §9.8.6) | Expand one tool; point at the Wazirabad→ITO step | The agent chooses the evidence and the chart form; the query is auditable | SSE `start → thinking → tool_start/tool_done → render → answer → done`; `createChartRenderer` | **LIVE — model required** (charts LIVE — deterministic) | §9.3, §9.4; live run completed | Nondeterministic tool choice → re-record the **same** question; charts may come from deterministic routes only if labelled |
| 2:30–2:50 (20 s) | 6 Honest answer | The answer card; the **grounding chip** "✓ Grounded — n figures verified against m retrieved"; read the `not_covered` line | Zoom the chip and read the limitation | The number check is demonstrated, with its limit | `grounding.check()` verdict on the `answer` event | LIVE — model required (verdict LIVE — deterministic) | `grounding.py`; live run grounded | Re-ask to force figures; or show a captured verdict |
| 2:50–3:10 (20 s) | 7 Honest label | The peak-offset result; **if the run did not surface it**, Terminal B: `curl -s "http://127.0.0.1:8000/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28"` — highlight `offset_days 9`, `health_points 4`, and the `caveat` | Read the caveat aloud, word for word | A descriptive offset between maxima is not causation | `officer.peak_offset()` | LIVE — deterministic | §9.4; live +9 d / 4 points | Always deterministic — safe |
| 3:10–3:40 (30 s) | 8 Handoff 1 — audit | Click **Transcript ↗** (opens in a new tab). Show the HTML: the request, **Action 1..n**, an expanded tool's **"Queries run"** FHIR URLs, the conclusion, and the grounding chip | Point at the step list and the FHIR URLs | **"How we reached it."** Attachable to an incident record | `GET /api/live/studio/transcript/{session}` → `studio_report()` | LIVE — session-dependent | live 200 OK, `Content-Disposition: attachment; filename="investigation-<session>.html"` | Pre-capture the session's transcript; recapture immediately |
| 3:40–4:10 (30 s) | 9 Handoff 2 — decide | Click **Executive report**; the browser **downloads** `surveillance-report-<session>.html`; open it from the downloads bar. Show the title, Situation, **Key findings** table with real values, **Recommended action**, **Limitations**, **Verification** chip, and the **embedded chart** from this run; click **Save as PDF** to show `window.print()` | Open the downloaded report; point at a real figure and the embedded chart | **"What leaders need to decide."** Same evidence, restructured | `POST /api/live/studio/executive {session, figures[]}` → `studio_executive()`; `studio.js executive()` blob-downloads it | LIVE — model required + session-dependent | live 200, `@page`, `window.print()`; **HTML not PDF; gateway sends no `Content-Disposition`** | Model error → narrate as a limitation; show `report/facts` (appendix) |
| 4:10–4:25 (15 s) | 10 Handoff 3/4 — reuse | Open **Readings CSV** in the downloads bar; show the header `…threshold, exceedance_factor, basis, observation_id`. Open **Health CSV**; show `…cases, population_at_risk, rate_per_100k, baseline_per_100k…`; place the two headers side by side | Point at the two different column sets | Two CSVs are different artifacts for different recipients: measurements vs denominators | `export_readings()`, `export_surveillance()` | LIVE — deterministic | §9.4 headers (live 200 + attachment) | Deterministic — safe |
| 4:25–4:32 (7 s) | 11 Handoff 5 — interoperate | Open the **FHIR Bundle** JSON; show `resourceType: Bundle`, `type: collection`, `meta.tag …|oah-demo-final`, and one `Observation.fullUrl` | Point at the four fields | Interoperable packaging, not a generic JSON download | `export_bundle()` | LIVE — deterministic | §9.4; live 200 + attachment; 422 without `site_id` | Deterministic — safe (requires station scope) |
| (fold into 12) | 12 Provenance + close | ~12 s provenance-note graphic: source → validation → screening → FHIR mapping → tagged transaction Bundle → live queries; then end card with the value sentence and boundaries | Trace the arrow, then hold on the end card | Records have a traceable origin; the story closes without overclaiming | (appendix covers the live walkthrough) | Bridge LIVE — deterministic; card n/a | §9.8, §9.10 | Bridge may be a generated graphic |

**Runtime arithmetic.** Scenes 0–11 sum to exactly **4:30 (270 s)**: 8 + 14 + 23 + 20 + 25 + 60 + 20 + 20 + 30 + 30 + 15 + 7 = 272 s, trimmed by merging the Scene-12 provenance bridge and close into the final beat so the recorded total lands at **≤ 4:30**. Recompute the total from the recorded clip lengths before assembly; if it exceeds 4:45, apply the §9.9 "total-runtime overflow" mitigation rather than shipping a longer cut. The hard ceiling remains **5:00**.

**Current-station vs all-stations (one line, Scene 1 or 4).** The scope selector is **Current station** /
**All stations**. Current station injects `Dashboard context: investigate station yam-ito…`; All stations does
not and the model typically picks a comparison form (`show_matrix`/`show_ranking`/`show_scatter`). The main cut
uses **Current station**; the all-stations comparison lives in the appendix.

**Explicit exclusions from the main cut.** No `?mode=mock` frame; the Relationships tab is never clicked; the
mock Reports workflow is never opened; no terminal transcript is presented as the agent (the agent is only ever
the real streamed Studio run, or a *clearly labelled* deterministic alternate shot).

---

## 9.6 Optional appendix storyboard (60–90 s, separate from the main total)

Record and assemble separately; **do not add to the main runtime**.

| Time | Segment | Screen | Purpose | Classification |
|---|---|---|---|---|
| 0:00–0:30 | Provenance end-to-end | Gateway logs / `POST /api/ingest-demo/iot` (or the no-write client-side variant, §9.8): validated → screened `[HIGH]` alert → mapped counts → tagged transaction Bundle → upload outcome | Show the identical code path a real source takes | LIVE WITH LIMITATIONS |
| 0:30–0:50 | Channel comparison | Convergence graphic + the three transports (MQTT topic, `ingestion.citizen_surveys`, `POST /ingest` / CSV) with their real identifiers | Three transports, one pipeline | LIVE WITH LIMITATIONS (graphic) |
| 0:50–1:05 | Different question, different chart | `show_matrix`, `show_scatter`, `show_ranking` rendered from the all-stations scope | The model's chart choice tracks the question | LIVE — deterministic (charts) |
| 1:05–1:20 | Model-free ground truth | `GET /api/officer/report/facts?days=28` and the deterministic analysis routes | The facts the model cannot alter; the offline fallback | LIVE — deterministic |
| 1:20–1:30 | Deterministic endpoint verification | `curl` of `wards`/`profile`/`offset` returning the same numbers without a model | Reproducibility by hand | LIVE — deterministic |

---

## 9.7 Complete presenter script

> Spoken narration only. `[bracketed]` lines are stage directions, not spoken. Read at a steady, measured,
> unhurried pace (~150–157 wpm). Do **not** read a window-sensitive number without naming its window. Do **not**
> read any figure that production has not re-derived immediately before recording (§9.4).

*[Title card: "One investigation, five usable handoffs."]*

**0:00** One river. One place. One officer with one question. On the Yamuna at ITO Bridge we have two completely
different kinds of evidence about the same place — and by the end, one investigation will leave five different
handoffs.

*[Open `http://127.0.0.1:8090/?mode=live`. Select the **Analyst** persona in the top-bar persona control — the Studio is offered only to Analyst.]*

**0:08** This is one investigation, not a tour. The dashboard is in live mode, reading a FHIR server through a
single dataset tag. That tag is how we know these records are ours on a server many people share. Everything on
screen from here is a real record, and it is synthetic demonstration data.

*[Context tab; scroll the observations.]*

**0:22** Same place, two kinds of evidence. Above the line, the water the environment agency measured — faecal
coliform, BOD, dissolved oxygen. Below it, the cases the health system notified — acute diarrhoeal disease.
Notice they do not arrive on the same clock: the water is sampled daily, the cases are reported weekly. Both
point at the same FHIR Location, and that difference in cadence matters in a moment.

*[Evidence tab; open one finding's drawer.]*

**0:45** The dashboard surfaces what deserves attention: a reading above a screening reference. Open it and you
get the actual FHIR Observation that was measured, and the rule it was screened against — here, the CPCB
bathing-water criterion of 2,500 per 100 millilitres, quoted from the screening code, not recalled by a model.
That "live-evidence" reference is a dashboard-level link; the record underneath is real.

*[Studio; scope = Current station; type the prompt.]*

**1:05** Now the part that matters. The officer does not click through stages — they ask a question. *[type]*
"Investigate the Yamuna at ITO Bridge over the last month." *[press Investigate]*

*[Watch the stream; expand one tool.]*

**1:30** Watch what it does. It starts by fetching the station profile, then the screening criteria — deliberately
first, so it never quotes a threshold from memory. Then it chooses its own tools: which data to pull, which
comparison to make, and which chart answers the question. A two-panel timeline here, the river in flow order
there, a persistence strip. Those charts are not sitting on a dashboard waiting; they are tools the model
picked. *[expand a tool]* Expand one and you see the exact FHIR query it ran, URL on screen, so you could
repeat it by hand — and notice it never writes that URL itself; it picks a checked tool and the code builds the
query, because an invented FHIR parameter returns an empty result that looks exactly like "no data."

*[Answer card; grounding chip.]*

**2:30** Before you trust any of it: every number in that answer was checked, mechanically, against the data the
tools actually returned — that is the green chip. And then it tells you what that does *not* mean: it checks
numbers, not sentences. A figure that is really in the data can still be used in a wrong sentence, and a claim
with no number in it is not checked at all. The software says so rather than letting a badge imply more than it
proves.

*[Offset card, or Terminal B `curl` of `/api/officer/offset`.]*

**2:50** Here is the honesty beat. The gap between the water peak and the notified-case peak is nine days — but
look at what the result calls itself: a *descriptive offset between two maxima, not a correlation*. Over
twenty-eight days there are only four weekly case reports. You cannot compute a meaningful correlation from four
points, and the software says so instead of pretending. Treat it as a prompt to sample — never a causal lag.

*[Click Transcript ↗.]*

**3:10** So the officer has an answer. But an answer is not a handoff. Same run — five things out the other
side. First, **how we reached it**: the transcript. The question, every step, every query it ran, the figures,
and the grounding verdict — attachable to an incident record so someone else can audit the route, not just the
result.

*[Click Executive report; it downloads `surveillance-report-<session>.html`. Open it and, if the run rendered charts, they are embedded.]*

**3:40** Second, **what leaders need to decide**: the executive report. Same evidence, rewritten as situation,
key findings, recommended action and limitations — with the actual charts from this run embedded, and a
print-to-PDF page. A Chief Medical Officer who was not in the room can act on it. It downloads as print-ready
HTML and saves to PDF from the browser; it is not a native PDF.

*[Open Readings CSV, then Health CSV; place headers side by side.]*

**4:10** Third and fourth, **what analysts and systems can reuse**: two different CSVs. The readings file
carries each measurement with its criterion, its screening basis, and the source Observation id. The
surveillance file carries cases, rates, and the population denominators behind them — district-wide, because
that is how surveillance is reported. Different recipients, different shapes. Retyping one file into the other
is exactly how denominators get lost.

*[Open the FHIR Bundle JSON.]*

**4:25** And fifth, for interoperable systems: this is not a generic JSON download. It is a tagged HL7 FHIR R4
**collection** Bundle of this station's evidence, scoped to our dataset tag — the format an ABDM-aligned
incident record can attach directly. It is a package of evidence, not a transaction, and it creates no new
resource on the server.

*[Provenance bridge graphic, then end card.]*

**4:32** And none of this appeared from nowhere. Each record has a traceable origin: validated, screened before
conversion, mapped to FHIR, tagged, wrapped in a transaction Bundle, uploaded — and then read back live.

**4:30 (close)** Same investigation, one officer, no retyping, provenance retained. Co-located records and a
descriptive offset are a signal worth investigating; they are not causation, and the available evidence does
not establish attribution. Confirmatory sampling is the next step, and that decision stays with the officer.
Synthetic data, prototype screening references. One river, two kinds of evidence — and five usable handoffs.

---

## 9.8 Recording runbook

All commands are repository-grounded. **Terminal A** = gateway, **B** = shell, **C** = dashboard. Use the repo
virtualenv (`/.venv`). Nothing here writes unless explicitly marked.

### 9.8.0 Stop conditions (do not record if any is true)

- `/api/info` reports a dataset tag other than `oah-demo-final`, or `/api/officer/trend?…yam-ito…` returns
  `points: 0` → the tag drifted; **restart the launcher, never re-seed**.
- The gateway cannot complete a real `studio/run` (model access unavailable) — the main cut needs Scenes 4–6;
  either resolve access or record the **clearly labelled** deterministic alternate and move Scenes 4–6 into it.
- Any export returns the wrong MIME/schema, or the FHIR bundle returns 422 with a `site_id` supplied.

### 9.8.1 Service and dependency preflight (read-only)

```bash
curl -s -m 5  http://127.0.0.1:8000/health            # {"status":"ok"}
curl -s -m 5  http://127.0.0.1:8090/health            # {"status":"ok", ...}
curl -s -m 20 http://127.0.0.1:8000/api/info | grep -o '"dataset_tag": *"[^"]*"'   # oah-demo-final
curl -s -m 60 "http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28" \
  | .venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print('points',d['points'],'latest',d['latest'])"
curl -s -m 60 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/api/live/sites/yam-ito   # 200
```

If the services are down, start them together from the repository root:

```bash
python run.py                 # loads the root .env; prints the dashboard/Studio address
# read-only demo (no MQTT/RabbitMQ consumers): python run.py --no-brokers
```

### 9.8.2 Verify the gateway's *effective* model access, not the shell's

The shell and the running gateway can differ. Verify access **through the gateway**, read-only, by running a
short investigation and confirming it streams tool calls and an answer rather than an `error` event:

```bash
curl -s -N -m 240 -X POST http://127.0.0.1:8000/api/officer/studio/run \
  -H 'Content-Type: application/json' \
  -d '{"question":"What needs attention at station yam-ito? Show the trend and the river profile."}' | head -c 4000
```

Expect `start → tool_start/tool_done → render → … → answer → done`. An `error` mentioning `OPENAI_API_KEY` means
the credential is not in the gateway's environment: set it in `.env` and **restart the gateway**, then repeat.
Do not film a stuck "Starting investigation…" panel.

### 9.8.3 Read-only FHIR checks (no writes)

```bash
curl -s -m 60 "http://127.0.0.1:8000/api/officer/wards?days=28" \
  | .venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print('priority',d['priority'])"
curl -s -m 60 "http://127.0.0.1:8000/api/officer/profile?river=Yamuna&indicator=faecal_coliform" \
  | .venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print('window',d['window_days'],'largest',d['largest_increase'])"
```

### 9.8.4 Browser, mode, and scope

- Open a clean window at `http://127.0.0.1:8090/?mode=live` (an explicit `?mode=` wins). Confirm the mode
  indicator reads **Live adapter** before every take. Keep the URL in the address bar visible at least once
  (Scene 1) so the live mode is on screen.
- **Select the Analyst persona** in the top-bar persona control. The Studio composer is disabled for every other
  persona (`studio.js allowed()`), and the **Surveillance** nav item is hidden until the session's capability
  `canQueryAssistant` is true (Analyst in live mode). Personas are a demo policy control, not authentication —
  that is stated on screen in the close.
- Station selector = **Yamuna at ITO Bridge**. Never open the **Relationships** tab; never touch the mock deck.
- Recording settings: 1920×1080, ≥30 fps, browser at 100 % zoom, bookmarks bar and personal tabs hidden, any
  credential blurred. Terminal font ≥ 16 px.

### 9.8.5 Exact Studio scope and prompt

- Scope: **Current station** (Yamuna at ITO Bridge).
- Prompt (type it on camera): `Investigate the Yamuna at ITO Bridge over the last month.`
- The dashboard appends `Dashboard context: investigate station yam-ito…` automatically.

### 9.8.6 How to get a run that visibly selects the intended tools (without faking it)

The model's tool choice is nondeterministic. **Warm the run once or twice before filming** with the same
truthful question, and if a take does not surface the trend and the river profile, **re-run the identical
question** — never edit terminal output to look like the agent, and never substitute a fabricated chart.
Charts render from tool specs, so a take that shows tool chips and two or three of the seven chart forms is a
valid run. Keep at least two good takes and cut the best.

### 9.8.7 Immediate transcript and report capture (before any restart)

Sessions are in memory and vanish when the gateway restarts. **Immediately** after the run you intend to use,
before doing anything else, capture the transcript and the report:

- On camera: click **Transcript ↗** (opens in a new tab), then **Executive report** (the browser **downloads** `surveillance-report-<session>.html`; open it from the downloads bar).
- As a safety copy (off camera), note the `session` id from the streamed `start`/`done` event and:
  ```bash
  SESSION=<id>
  curl -s -m 60  "http://127.0.0.1:8000/api/officer/studio/report/$SESSION"    -o /tmp/transcript.html
  curl -s -m 240 -X POST "http://127.0.0.1:8000/api/officer/studio/executive" \
    -H 'Content-Type: application/json' -d "{\"session\":\"$SESSION\",\"figures\":[]}" -o /tmp/executive.html
  ```
  Both are read-only. The executive report's on-camera version should carry the embedded charts; the safety copy
  with `figures: []` is a fallback.

### 9.8.8 Opening the two CSVs and the FHIR Bundle cleanly

Browsers may auto-open CSV/JSON. Download first, then open from the downloads bar so the header row is a clean
shot. The **FHIR Bundle link only renders in station scope** (`siteId` set) — keep scope = Current station. The
**Executive report** is likewise a blob download (`surveillance-report-<session>.html`) — open it from the
downloads bar, not by URL. Direct routes for a controlled capture:

```bash
curl -s -m 120 "http://127.0.0.1:8090/api/live/studio/export/readings?days=28&site_id=yam-ito" -o /tmp/readings.csv
curl -s -m 120 "http://127.0.0.1:8090/api/live/studio/export/surveillance?days=90"              -o /tmp/surveillance.csv
curl -s -m 120 "http://127.0.0.1:8090/api/live/studio/export/fhir?days=28&site_id=yam-ito"      -o /tmp/bundle.json
```

On screen, show the **readings** header (`…threshold, exceedance_factor, basis, observation_id`) and the
**health** header (`…cases, population_at_risk, rate_per_100k, baseline_per_100k…`) side by side, and the
**Bundle** fields `resourceType`, `type: collection`, `meta.tag`. Do not freeze transient row counts into
narration.

### 9.8.9 Cache and refresh behaviour

- Gateway overview cache: `OVERVIEW_CACHE_SECONDS` (default 60); `?refresh=true` bypasses it; a successful
  upload invalidates it.
- Browser: `api.js` holds a per-station `liveStationCache`. Hard-refresh (**F5**) before asserting "the new
  record appears".
- Studio sessions do **not** survive a gateway restart (transcript/report then 404).

### 9.8.10 Terminal layout, where needed

Only two terminal moments exist in the main cut: the **offset fallback** (Scene 7) and, briefly, nothing else.
Everything else is product UI. Keep Terminal B narrow and readable; keep Terminal A (gateway logs) off-screen
unless recording the appendix provenance walkthrough.

### 9.8.11 Media capture order

1. Preflight (§9.8.1–9.8.3). 2. Warm the Studio run (§9.8.6). 3. Capture the Studio scenes (4–6). 4. Immediately
capture transcript + report (§9.8.7). 5. Capture context/evidence (Scenes 1–3) and the offset (Scene 7).
6. Capture the exports (Scenes 10–11). 7. Capture the provenance bridge and cards (Scene 12, §9.10). 8. Assemble,
then verify duration, captions and boundaries (§9.12).

### 9.8.12 Reset and recovery

```bash
./run-demo.sh down                 # stop RabbitMQ if it was started
# restart the gateway to reload env, clear the overview cache, and drop Studio sessions
# then F5 the browser to clear api.js caches
```

If a scene fails: hard-refresh; confirm the backend with the matching `curl`; if the live scene still will not
load, use the **deterministic live fallback shown in that scene** and **label it aloud**. Never switch to
`?mode=mock` to recover, and never fabricate a Studio result.

### 9.8.13 When production must stop rather than substitute

Stop and report (do not ship a misleading cut) if: the model credential is unavailable for the Studio scenes and
the operator is unwilling to record the labelled deterministic alternate; the dataset tag has drifted; the story
station has no observations for the window; or an artifact's response does not match its expected MIME/schema.

---

## 9.9 Demo risk checklist

| Risk | Why it matters | Preflight check | Mitigation / approved fallback |
|---|---|---|---|
| Model unavailable or nondeterministic tool choice | Scenes 4–6 are the centrepiece; the choice is not fixed | Run one short `studio/run` through the gateway (§9.8.2) | Warm the run; re-run the identical truthful question; if access is truly absent, record the **clearly labelled** deterministic alternate and say so — never fake the agent |
| Studio session loss | Transcript/report 404 after a restart | Do not restart the gateway mid-capture | Capture transcript + report **immediately** (§9.8.7) |
| Executive-report failure | Scene 9 depends on a model call | Run it once off camera; confirm HTML with `@page`/`window.print()` | Re-run; if it fails, narrate as a limitation and show `report/facts` in the appendix. The gateway sends **no attachment header**; `studio.js` **downloads** `surveillance-report-<session>.html` — expect a downloads-bar entry, not a new tab |
| FHIR availability | Every live scene and export fails | `curl $FHIR_BASE_URL/metadata?_summary=true` | Retry; `FHIR_RETRIES` handles transient stalls; recapture |
| FHIR tag mismatch | A restart under a different tag hides ITO | `/api/info` tag == `oah-demo-final`; `trend yam-ito` `points 28` | **Restart the launcher to reload `.env`; never re-seed** |
| Live value drift | Window-sensitive numbers change (profile 14 d vs 28 d) | Re-derive every value in §9.4 immediately before recording | State the window per number; re-derive, do not reuse an older table |
| Stale overview / browser cache | A just-changed view does not appear | `?refresh=true`; F5 | Hard-refresh before asserting a record appears |
| Shared-server contamination | Public HAPI holds others' `oah-demo*` resources | Narrate the tag; total is tag-scoped | Never claim ownership of all `oah-demo*`; for any write use a unique tag or an isolated server |
| Mock/live confusion | Breaks the promise instantly | Confirm `?mode=live` + **Live adapter** every take | Never open the mock deck; state the boundary in words in the close |
| Artifact download/open behaviour | CSV/JSON may auto-open; the report and CSVs are downloads | Test one download per artifact beforehand | Download-then-open for a clean header shot; the report downloads as `surveillance-report-<session>.html` (HTML, not PDF) |
| Studio persona gate | The composer is disabled unless the **Analyst** persona is selected | Confirm Analyst is chosen and the Surveillance nav item is visible | Select Analyst in the persona control; the gate is a demo policy, stated on screen — never presented as production auth |
| Row-count drift | Exports are deterministic but their counts depend on the tag/window | Show the header row, not the count, unless re-derived | Never freeze row counts into narration |
| Missing observations | A station view 404s | Deep-link only verified stations; confirm `/api/live/sites/yam-ito` is 200 | Use `yam-ito`; do not point the camera at unverified stations |
| Accidental causal overstatement | The entire scientific point | Re-read the caveats; scan narration for banned phrases | Never say "caused", "proves a lagged effect", "identifies the discharge", "legal limit", "a real event". Use "screened against the prototype reference", "the largest change appears between these monitored stations", "a descriptive offset between maxima", "the available evidence does not establish attribution or causation" |
| Dashboard co-location ≠ Studio co-location | The dashboard tile never fires for ITO (no risk scores); the Studio's test is different | Know both before recording | Narrate them as different computations; never imply the tile corroborates the Studio |
| Total-runtime overflow | Hard ceiling 5:00 | Sum the recorded clip lengths before assembly | Trim Scene 5 or Scene 9; keep the appendix separate; never ship >5:00 |

---

## 9.10 Visual and editorial plan

Product interfaces and real artifacts stay central. Supporting graphics are minimal and annotate what the
interface already shows. **No slide, card, or still may show mock fixtures, the relationship graph, a generated
report, or a generated persona-control mock-up, and no frame may synthesize the product UI.** (The real dashboard
persona control *is* recorded — Scenes 1 and 4 — because selecting the Analyst persona is part of the real flow;
what is banned is a fabricated persona graphic.)

1. **Opening title** (Scene 0): "One investigation, five usable handoffs" / "Yamuna at ITO Bridge — synthetic
   demonstration dataset" / a thin strip: 💧 Environmental measurements · 🏥 Notified population health · ⇄ HL7
   FHIR R4. ≤5 s on screen.
2. **Recipient/handoff overlay** (Scenes 8–11): a restrained lower-third per artifact naming the recipient and
   the job — *"Auditor — how we reached it" · "DSO / CMO — what leaders need to decide" · "Analyst — what can be
   reused" · "ABDM / FHIR system — what systems can reuse"*. One line at a time; never a full-screen slide.
3. **Concise provenance bridge** (Scene 12): one arrow — source → validation → screening (before conversion) →
   FHIR mapping → tagged **transaction** Bundle → upload → live FHIR reads — labelled with the real identifiers
   where short enough.
4. **Boundary / end card** (Scene 12): the value sentence plus "Synthetic demonstration data · prototype
   screening references · shared HAPI FHIR sandbox", and "Association, not causation."
5. **Optional small annotations** (only if they add clarity without obscuring the UI): a zoom box on the
   grounding chip's `not_covered` line (Scene 6); a zoom box on the tool expansion's FHIR URL (Scene 5); a
   two-header comparison of the CSVs (Scene 10).
6. **Banned from graphics:** any correlation/regression line; any pin implying a specific discharge; any
   generated report image; any mock UI.

---

## 9.11 Demo truth matrix

| Demo claim | Classification | Code/runtime evidence | Safe narration | On-screen proof |
|---|---|---|---|---|
| The dashboard reads live tagged FHIR through the gateway | LIVE WITH LIMITATIONS | `server.proxy_live()`; `web.overview()/site_detail()`; `briefing.dataset_briefing()` | "Read live, scoped to a dataset tag — assuming the gateway is on the matching tag." | Mode indicator + scope line |
| The view is scoped by `oah-demo-final` | LIVE | `pipeline.dataset_tag()`; `bundle.tag_resources()` | "One tag scopes every query, so on a shared server we see our records." | Scope line; Bundle `meta.tag` |
| ITO has environmental + health records at one Location | LIVE | live 140 env + 16 health; `site_detail` 200 | "Both streams cite the same FHIR Location." | Context tab rows |
| The `live-evidence-*` links are real FHIR `Evidence` | **NOT IMPLEMENTED** (dashboard-level references) | `api.js liveEvidenceId()`; resolver re-fetches the station | "A dashboard-level reference; the record underneath is a FHIR Observation." | Drawer record types |
| The dashboard's co-location tile fires for ITO | **NOT IMPLEMENTED** (needs `elevated_risk`; India has none) | live `sites_with_co_location: []` | "The dashboard's co-location needs a risk classification ITO's series does not have." | Never shown firing |
| The Studio finds ITO co-located | LIVE | `officer.wards()` `co_located` = exceedance AND ADD rise >15%; live `+140.4%` | "The Studio uses a different test — a screening flag plus a rise in notified cases." | Wards tool summary |
| Trend/change is computed, not narrated | LIVE — deterministic | `officer.trend()`; live `+84.9%`, latest `25070` vs `2500` | "Computed in Python: the most recent 14 days against the 14 before." | Trend chart; change basis string |
| The ward ranking exists | LIVE — deterministic | `officer.wards()` | "Every ward screened and ranked." | Tool summary |
| The river profile localises a stretch | LIVE WITH LIMITATIONS | `officer.river_profile()`; **window-sensitive** step | "Over the last fourteen days the largest change appears between these monitored stations — it narrows where sampling may help; it does not identify a discharge." | Profile chart + window |
| Exceedance persistence | LIVE — deterministic | `officer.persistence()`; live 28/28 | "A sustained condition, not a one-off." | Persistence strip |
| The peak offset is a correlation/lagged effect | **NOT IMPLEMENTED** (descriptive) | `officer.peak_offset()`; `health_points 4`; caveat | "A descriptive offset between maxima — nine days, four weekly points — a prompt to sample, not a causal lag." | Offset card + caveat |
| Screening thresholds are legal limits | **NOT IMPLEMENTED** (prototype references) | `thresholds.py` docstring; `as_reference()` note | "A prototype screening reference — not a statutory limit." | Basis string |
| Numeric grounding verifies the answer | LIVE WITH LIMITATIONS | `grounding.check()`; live run grounded | "It checks that every number appears in the retrieved data — not that the sentence is right, and not number-free claims." | Grounding chip + `not_covered` |
| The Studio picks the chart, not the dashboard | LIVE — model required | `STUDIO_SCHEMAS`; `SYSTEM` | "Which chart answers the question is a decision the model makes." | Streamed render events |
| The model never writes a FHIR URL | LIVE — design property | `tools.py`; `SYSTEM` | "It picks a typed tool; the code builds the query." | Expanded tool URL |
| The transcript is the audit trail | LIVE — session-dependent | `officer.studio_report()`; `Content-Disposition: attachment` | "The transcript itself — how we reached the conclusion." | Transcript HTML |
| The executive report is a decision handoff | LIVE — model required | `officer.studio_executive()`; `EXEC_PROMPT` | "Same evidence, restructured for a decision-maker — print-ready HTML, saved to PDF from the browser." | Report sections + `window.print()` |
| The executive report is a native PDF | **NOT IMPLEMENTED** | `HTMLResponse`, no attachment header | "Print-ready HTML, not a native PDF." | Browser tab + Save-as-PDF |
| The executive report is *opened* by the dashboard | **NOT IMPLEMENTED** (it is downloaded) | `studio.js executive()` blob-downloads `surveillance-report-<session>.html` | "The dashboard downloads it; open it and print to PDF." | Downloads-bar entry |
| Readings CSV and health CSV are different artifacts | LIVE — deterministic | `export_readings()` vs `export_surveillance()`; verified column sets | "Different recipients, different shapes." | Two headers side by side |
| The FHIR export is an `Evidence` resource / a transaction | **NOT IMPLEMENTED** | `export_bundle()` → `type: collection` | "A packaged collection of the station's evidence — not a transaction, and it creates no new resource." | `resourceType`/`type`/`meta.tag` |
| Ingestion sample runs the real pipeline | LIVE WITH LIMITATIONS | `web.ingest_demo()` → `process()`; live alert + mapping | "The same code path a real source takes." | Appendix |
| Citizen surveys become `QuestionnaireResponse` | **NOT IMPLEMENTED** | `fhir_adapter.citizen_survey_to_fhir()` → `Observation` | "Survey answers map to OAH-profiled Observations." | Appendix (if shown) |
| The `oah-demo*` tag is a risk/analysis class | **NOT IMPLEMENTED** | `bundle.tag_resources()` | "A dataset scope tag, not a risk class." | Scope line; Bundle `meta.tag` |
| The Studio runs for any persona | **NOT IMPLEMENTED** (Analyst only) | `studio.js allowed()` = `apiMode==="live" && state.role==="analyst"` | "The Studio opens for the Analyst persona — a demo policy control, not authentication." | Composer enabled only under Analyst |
| Production authentication / persona scope | **NOT IMPLEMENTED / MOCK** | gateway anonymous; `api.js liveSession()` | "Neither interface implements production authentication." | (statement only) |
| The synthetic data is a real event | **NOT IMPLEMENTED** (synthetic) | `generate_timeseries.py`; sites.json comment | "Synthetic demonstration data — the method is real, the readings are not." | Title/end card |

---

## 9.12 Acceptance criteria

Pass/fail, checked against the assembly:

- [ ] **Runtime** between 3:00 and 5:00 (state the exact duration; target ≈4:30).
- [ ] A **real live Studio run** is shown (streamed tool calls, not terminal output standing in for the agent).
- [ ] At least **one tool's `arguments` and FHIR evidence URL** are visible on screen.
- [ ] At least **two model-selected visual forms** are shown (e.g. two-panel trend + river profile).
- [ ] The **grounding verdict and its `not_covered` limitation** are visible.
- [ ] The **transcript** is opened.
- [ ] The **executive report** is opened with this run's actual figures and an embedded chart.
- [ ] The **readings CSV and health CSV** are visibly distinguished (different headers on screen).
- [ ] The **FHIR Bundle** shows `resourceType`, `type: collection`, and the dataset tag.
- [ ] **No mock-only capability is presented as live**; the Relationships tab and mock Reports are never shown.
- [ ] **Synthetic-data and association-not-causation boundaries** are both spoken and visible.
- [ ] **No stale number** is used: every window-sensitive value names its window and was re-derived before
      recording.
- [ ] **No generated product UI**: every product frame is a real recording of the running interface.

---

*End of plan. Produced read-only on branch `feature/data-fix-and-video-story` @ `a2d377b`. No application code,
configuration, fixtures, source data, or existing media were modified. Only this file and
`oneaquahealth-video-generation-prompt.md` were replaced.*
