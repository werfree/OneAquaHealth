# Surveillance Studio — capability audit and story revision

**Status:** investigation only. No application code, data, configuration, or video asset was modified.
No replacement video was generated. This document is a proposal for approval.

**Method:** evidence-led. Every claim below is backed by a file/symbol/route citation and, where possible, a
read-only live check. Live checks were run on 2026-10-04 against the running stack:

- gateway `http://127.0.0.1:8000` (`/health` → `{"status":"ok"}`; `api/info` → FHIR
  `https://hapi.fhir.org/baseR4`, dataset tag **`oah-demo-final`**)
- evidence dashboard `http://127.0.0.1:8090` (`/health` → ok)
- a model key **is present in the gateway's environment** (a full Studio run completed successfully) even
  though `OPENAI_API_KEY` is not exported in an interactive shell.

Legend for **Classification** (exactly one per row): `LIVE — deterministic` · `LIVE — model required` ·
`LIVE — session-dependent` · `LIVE WITH LIMITATIONS` · `MOCK / SIMULATED` · `NOT IMPLEMENTED` · `UNVERIFIED`.

---

## 1. Executive finding

**What the system truly does.** The Studio is not a dashboard tour and not a chat box. It is a *complete
district-surveillance investigation loop whose every stage is auditable*: a question → typed FHIR tool calls
whose URLs the model is forbidden to invent → Python-computed analyses → model-chosen charts → a numerically
grounded conclusion → and then **four different handoff artifacts** produced from the *same* transcript
(investigation transcript, executive situation report, environmental readings CSV, health-surveillance CSV)
plus one interoperable one (**a tagged FHIR R4 collection Bundle**). A district surveillance officer can
therefore act on a finding, hand it to a Chief Medical Officer, hand numbers to an analyst, and hand a
machine-readable record to an ABDM-aligned system — **without retyping anything and without losing provenance
or overstating causality.**

**What the existing video under-communicates.** The current cut (≈4:18, 10 scenes) is built around a strong
but *narrow* idea — "one river, two kinds of evidence." It convincingly shows the live dashboard and the
ingestion pipeline, and it correctly refuses to overclaim. But on the dimension the repository has invested
most in lately it shows almost nothing:

- **Scenes 5–7 (the Studio run) were recorded against a deterministic fallback, not the agent.** The
  shot-list states `OPENAI_API_KEY` is not set and directs the recorder to film `curl` output. So the
  single most distinctive capability — *the model choosing which data to pull and which chart answers the
  question, streaming its work as it goes* — is **documented but never actually shown**.
- **The grounding receipt is described in narration, never demonstrated.** There is no shot of the green
  "✓ Grounded — n figures verified against m retrieved" chip, and nothing explains what it does *not* prove.
- **The entire post-investigation handoff is invisible.** The video never opens the transcript, never opens
  the executive report, never downloads either CSV, and never opens the FHIR Bundle. The reader is told a
  report exists; they never see one.
- **The two CSVs are never distinguished**, and the FHIR Bundle is never explained as more than "a
  download."
- **Current-station vs all-stations investigation is never contrasted**, even though the UI exposes a scope
  selector and the system treats them differently.

**The single most important narrative change.** Keep the investigation, but **make the handoff the payoff.**
The current arc ends on a convergence graphic and a disclaimer; the stronger arc ends on *the same
investigation becoming five artifacts, each addressed to a different person or system* — transcript for the
auditor ("how we reached it"), executive report for the decision-maker ("what leaders need to decide"), the
two CSVs and the FHIR Bundle for analysts and interoperable systems ("what can be reused"). That single
reframing converts a feature tour into an **operational workflow**, and it is the one thing the current cut
cannot communicate because it never opens an artifact.

---

## 2. Complete capability inventory

Grouped as requested. Classification is exact; "Visible today?" = does the current video show it.

### 2.1 Data retrieval and context (the model's allow-listed FHIR tools)

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| `get_thresholds(city)` — screening criteria + regulatory basis | `LIVE — deterministic` | Stops the model quoting a "safe level" from memory | `oah_agent/tools.py get_thresholds()` → `oah_ingestion/thresholds.as_reference()` | Mentioned; the *value* is on screen in Scene 3, not the tool | None (pure Python) | Prototype screening references; Indian cities use CPCB/IS 10500, European cities differ | **Show** it as the first tool the agent calls, with basis |
| `list_sites()` — every monitored site + city + GPS | `LIVE — deterministic` | Resolves "this station" | `tools.list_sites()` → FHIR `Location?_tag=…` | No | Reachable FHIR + correct tag | `_count=200`; gazetteer only fills city for known ids | Keep out of main cut |
| `search_observations(kind, indicator, site_id, min/max, since/until, limit)` | `LIVE — deterministic` | The retrieval primitive behind every number | `tools.search_observations()`, typed profile + `_tag` scope | No | FHIR + tag | Client-side value filter (component stats); cap 200 | Worth adding if time permits |
| `get_site_profile(site_id)` — env + health + cohorts (One Health join) | `LIVE — deterministic` | One call puts chemistry next to population health | `tools.get_site_profile()` (3 searches) | No | FHIR + tag | Issues 3 searches; no temporal alignment | Worth adding if time permits |
| `get_cohort(group_id)` — cohort demographics | `LIVE — deterministic` | Explains *who* a health measure describes | `tools.get_cohort()` → FHIR `Group` | No | FHIR + tag | Returns `error` dict if absent | Keep out of main cut |
| Typed-tool design: the model never writes a FHIR URL | `LIVE — deterministic` (design property) | Prevents plausible-but-empty FHIR queries | `tools.py` module docstring; `search_url()`; system prompt forbids URLs | No (stated in narration only) | — | — | **Must add** — it is the single clearest safety property |

### 2.2 Analytical computation (deterministic, Python-side; no model needed)

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| `trend(site, indicator, days)` + period change | `LIVE — deterministic` | "What moved, by how much" | `officer.trend()`; midpoint split (not last-7) | Narration only | FHIR + tag | Change is mean-vs-mean of window halves | **Must add** (numbers on screen) |
| `wards()` — rank wards by exceedance + case rise, `co_located` flag | `LIVE — deterministic` | Tuesday-morning triage order | `officer.wards()`; 60 s `_WARDS_CACHE` | Narration only | FHIR + tag | `co_located` = exceedance **AND** ADD rise >15 % (a *different* test from the dashboard) | **Must add** |
| `river_profile(river, indicator, days)` + largest step | `LIVE — deterministic` | Localises the stretch a load enters on | `officer.river_profile()`; `sites.flow_km` order | Described, charted in fallback | FHIR + tag | "Step narrows where; does not identify a discharge" | **Must add** |
| `persistence(days, indicator)` — days-over + longest run | `LIVE — deterministic` | One-off vs sustained condition | `officer.persistence()`; per-date dedupe | Described | FHIR + tag | Run = consecutive *sampling* days | **Must add** |
| `peak_offset(site, indicator, days)` — descriptive offset + caveat | `LIVE — deterministic` | Honest temporal comparison | `officer.peak_offset()` | Shown (best scene in the cut) | FHIR + tag; ≥14 d | Descriptive, `health_points` usually 4; **not** a correlation | Keep (already strong) |
| `report_facts(days)` — the derived facts with no model call | `LIVE — deterministic` | Ground truth for the executive report; offline fallback | `officer._report_facts()` | No | FHIR + tag | — | Worth adding if time permits |

Verified live values (`oah-demo-final`, read-only): trend ITO coliform latest **25 070** MPN/100 mL vs
**2 500** criterion, 14-day change **+84.9 %**; wards priority `['yam-ito']`, ADD **+140.4 %**; profile
largest step Wazirabad→ITO **42.59× / 12 km** (recomputed today; plan §5 quotes 32.84× — see §8);
persistence yam-ito **28/28**, longest run 28; offset **+9 d**, `health_points 4`.

### 2.3 Agent orchestration

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| Streamed investigation (SSE): `start → thinking → tool_start/tool_done → render → answer → done` | `LIVE — model required` | Officer watches reasoning, not a spinner | `studio.run()`; `officer.studio_run()`; `dashboard/server.live_studio_run()` | Partially (fallback only) | **`OPENAI_API_KEY`** | Streams reasoning as it happens; `MAX_ROUNDS=10` | **Must add** — the centrepiece |
| Model **chooses tools and chart form** (`show_trend` vs `show_matrix` vs `show_scatter` …) from the question | `LIVE — model required` | "Which chart answers this" is a reasoning step | `STUDIO_IMPLEMENTATIONS`/`STUDIO_SCHEMAS`; `SYSTEM` prompt | No | key | Two or three well-chosen views preferred by prompt | **Must add** |
| Argument repair (`window_days→days`, `station→site_id`, drop unknown) | `LIVE — deterministic` | A guessed arg costs a retry, never the call | `studio._clean()`, `_ALIASES`; tested in `test_studio.py` | No | — | — | Keep out of main cut |
| In-memory sessions | `LIVE — session-dependent` | Lets the follow-on downloads resolve | `studio.SESSIONS` | No | — | **Lost on process restart**; no TTL; not shared across workers | Must be stated as a limitation |
| Dashboard appends station context to the question | `LIVE — deterministic` | Makes "current station" precise | `dashboard/server.live_studio_run()` | No | — | Context injection, not a hard filter | Worth adding if time permits |

### 2.4 Visual explanation (chart tools → browser-rendered SVG)

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| 7 render types: `stats`, `matrix`, `ranking`, `trend`, `scatter`, `profile`, `persistence` | `LIVE — deterministic` | Each answers a *different* question | `studio-charts.js createChartRenderer()` | trend/profile/persistence in fallback; matrix/scatter/ranking never | Browser only | Tool returns a spec; the browser draws it | **Must add** — show ≥2 forms side by side |
| Two aligned panels, **never a dual y-axis** | `LIVE — deterministic` | Coliform (10⁴) and cases (10¹) stay honest | `drawTrend()` | Yes | — | — | Keep |
| Log-scale river profile + step callouts; persistence strip; scatter's "association not causation" legend | `LIVE — deterministic` | Encodes the caveats in the graphic itself | `drawProfile()`, `drawPersistence()`, `drawScatter()` | Partly | — | — | Worth adding if time permits |

### 2.5 Grounding and auditability

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| Numeric grounding verdict (every figure checked against retrieved data) | `LIVE — deterministic` | "Did it make this up?" is checked, not asked | `grounding.check()`; verdict attached to `answer` | **No — described only** | — | Checks numeric literals only; a grounded figure can still sit in a wrong sentence; number-free claims unchecked | **Must add** — show the chip *and* its `not_covered` text |
| Grounding sources include chart specs and query arguments | `LIVE — deterministic` | Charts are evidence too; "the past 28 days" is a fact | `studio.run()` appends `result`, `args`, `render`; `test_studio.py` | No | — | Deliberate: arguments are facts, **not** a licence to quote a filter as a threshold | Worth adding if time permits |
| Visible FHIR evidence links + tool arguments per step | `LIVE — deterministic` | Any claim can be re-run against the server by hand | `tool_done` carries `urls` + `arguments` | Partly (one expansion) | — | — | **Must add** |

### 2.6 Reports and handoffs

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| **Investigation transcript** (HTML) | `LIVE — session-dependent` | Auditability: *how* the conclusion was reached | `officer.studio_report()`; `dashboard` proxy `transcript/{session}` | **No** | Valid in-memory session | 404 after restart; self-contained HTML, **not** PDF | **Must add** |
| **Executive situation report** (HTML, print-styled) | `LIVE — model required` | Decision-makers: findings, actions, limitations, figures | `officer.studio_executive()`; `EXEC_PROMPT`; JSON-mode model call | **No** | **key** + valid session | **Print-ready HTML with browser Save-as-PDF — not a native PDF.** Re-grounds the report text | **Must add** |
| Executive report embeds the run's actual chart SVGs | `LIVE — session-dependent` | The report carries the charts the analyst chose | Browser posts `figures[]` (SVG) to `/studio/executive` | **No** | SVGs from the live DOM | Max 30 figures | **Must add** (it is visible proof the report is *from* this run) |
| Deterministic facts behind the report (`report_facts`) | `LIVE — deterministic` | Model writes prose over facts it cannot alter | `officer._report_facts()` | No | FHIR + tag | — | Worth adding if time permits |

Verified live: transcript (12 098 bytes, `Content-Disposition: investigation-<session>.html`, 4 actions,
3 query blocks, "Grounded — 6 figures"); executive report (9 002 bytes, titled *"Yamuna River at ITO Bridge
Water Quality Exceedances"*, sections Situation / Key findings / Recommended action / Limitations /
Verification).

### 2.7 CSV / FHIR interoperability

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| **Environmental readings CSV** | `LIVE — deterministic` | Analysts: readings + criterion + basis + Observation id | `officer.export_readings()` | **No** | FHIR + tag | Station-scoped if `site_id`; else all | **Must add** |
| **Health-surveillance CSV** | `LIVE — deterministic` | Preserves cases, denominators, rates | `officer.export_surveillance()` | **No** | FHIR + tag | **District-wide only** (no `site_id` param) | **Must add** |
| **Tagged FHIR R4 collection Bundle** | `LIVE — deterministic` | Native attach to an ABDM-aligned incident record | `officer.export_bundle()` | **No** | FHIR + tag + **`site_id` required** | `type: collection`; `meta.tag` = the dataset tag; single station | **Must add** |

Verified live headers/artifacts:
readings CSV → `text/csv`, filename `oah-readings-yam-ito-28d.csv`, columns
`date,site_id,station,district,indicator,value,unit,threshold,exceedance_factor,basis,observation_id`, 141 rows;
health CSV → `text/csv`, filename `oah-surveillance-90d.csv`, columns
`date,site_id,station,district,cohort,condition,cases,population_at_risk,rate_per_100k,baseline_per_100k,observation_id`, 97 rows;
FHIR Bundle → `application/fhir+json`, filename `oah-evidence-yam-ito-28d.json`, `resourceType Bundle`,
`type collection`, `total 156`, `meta.tag [dataset-tag|oah-demo-final]`, all entries `Observation`.

### 2.8 Ingestion / provenance that directly supports the Studio story

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|
| `ingest_demo(key)` — sample through the real pipeline, returning every stage | `LIVE WITH LIMITATIONS` | Proves the records the Studio read have a traceable origin | `web.ingest_demo()` | **Yes (Scene 8)** | FHIR server (writes unless upload disabled) | Response shows `observations[:4]`; `upload.resources` counts built entries (Location deduped) | Shorten, keep the alert + mapped counts |
| Typed envelope → screening → FHIR mapping → tagged transaction Bundle → upload | `LIVE — deterministic` | The identical code path a real sensor takes | `pipeline.process()`, `fhir_adapter`, `bundle.py`, `fhir_client` | Yes | Reachable FHIR for upload | No retry/outbox on upload failure | Keep (compressed) |
| MQTT / RabbitMQ / HTTP+CSV channels | `LIVE WITH LIMITATIONS` | Three transports, one pipeline | `mqtt_worker`, `rabbitmq_worker`, `web` | Yes (graphic) | Brokers for a live message | Defaults are shared/public services | Keep (graphic) |

### 2.9 Deliberately excluded from the live story

| Capability | Classification | Why it is excluded |
|---|---|---|
| Relationship graph | `MOCK / SIMULATED` | `server.get_graph()` reads fixtures; live gateway has no graph route (`api.js` → 501) |
| Mock report lifecycle + downloads | `MOCK / SIMULATED` | `server.create_report()`/`report_html()` are local demo only; **separate** from the Studio's live report/transcript |
| Durable run history / retry | `NOT IMPLEMENTED` | `api.js liveAdapter.runs` returns `[]`; retry 501 |
| Persona authorization | `MOCK / SIMULATED` | `server.require()` enforces in mock; live `liveSession()` expresses *intended* capability only; no production auth |
| Dashboard `live-evidence-*` as FHIR `Evidence` resources | `NOT IMPLEMENTED` | `api.js liveEvidenceId()` builds dashboard-level references; underlying record **is** a FHIR Observation |
| Dashboard "co-located sites" finding firing for ITO | `NOT IMPLEMENTED` | Needs exceedance **and** `elevated_risk`; the Indian series has no risk scores. The Studio's `co_located` uses a *different* test |

---

## 3. End-to-end traces

> Route chain notation: `UI action → dashboard proxy → gateway route → core fn → data source → output`.

### 3.1 One current-station investigation

- **UI:** Studio composer, scope = **Current station** (station chip = "Yamuna at ITO Bridge"); type a question,
  press **Investigate**. `dashboard/static/js/studio.js run()`.
- **Chain:** `POST /api/live/studio/run` → `dashboard/server.live_studio_run()` (validates, appends
  `Dashboard context: investigate station <id>`) → `POST /api/officer/studio/run` → `oah_agent.studio.run()`
  (SSE) → tool loop calls `STUDIO_IMPLEMENTATIONS` → `oah_ingestion.officer` routes.
- **Core functions:** `study.run()`; `rank_wards/get_trend/show_*`; `officer.trend/wards/river_profile/
  persistence`; `grounding.check()`.
- **Data source:** live FHIR `Observation` reads scoped by `_tag` (`oah-demo-final`), profiles
  `observation-indicators-oah` / `-with-component-` / `-health-measure-oah`.
- **Output:** streamed `start/thinking/tool_start/tool_done/render/answer/done`, browser-rendered SVG charts,
  grounding chip, session id.
- **Failure/session behavior:** no key → `data:{"type":"error", … "OPENAI_API_KEY …"}`; unknown tool →
  `{error}` fed to the model; session **in memory** (lost on restart); Stop aborts the browser request only.

### 3.2 One all-stations comparison

- **UI:** scope selector → **All stations** (`scope.value = "all"` ⇒ `siteId = null`). Chips marked
  `data-studio-all` ("Compare wards", "Persistence") auto-select it.
- **Chain:** identical to 3.1 but the proxy **omits** the station-context line; the model typically selects
  `show_matrix` / `show_ranking` / `show_scatter` (all call `officer.wards()`).
- **Output:** district grid / ranking / scatter across all 17 gazetteer sites; `priority` list.
- **Behavior:** same session semantics. The distinction is real: station scope injects a station id; all-stations
  does not.

### 3.3 Transcript generation

- **UI:** `GET /api/live/studio/transcript/{session}` (link "Transcript ↗", opens in a new tab).
- **Chain:** → `officer.studio_report()` → `oah_agent.studio.session()`.
- **Output:** self-contained HTML built **from the transcript itself** (request, each `thinking`, each `tool`
  with `Queries run` URLs and render note, conclusion + grounding chip + footer). `Content-Disposition:
  attachment; filename="investigation-<session>.html"`, `text/html`.
- **Failure:** 404 if the session is gone ("it may have expired with the process").

### 3.4 Executive-report generation

- **UI:** "Executive report" button in the post-run download row → `studio.js executive()` collects every
  `.viz` SVG (inlines computed fill/stroke/font styles) and posts them.
- **Chain:** `POST /api/live/studio/executive {session, figures[]}` → `officer.studio_executive()` →
  `EXEC_PROMPT` JSON-mode model call over the transcript (summaries + reasoning, **not** the raw mechanics).
- **Output:** print-styled HTML (`@page A4`, Save-as-PDF button `window.print()`), sections Situation / Key
  findings table / Assessment / Figures / Recommended action (sorted by urgency) / Limitations / Verification
  chip / signature lines / appendix of evidence queries.
- **Failure:** 404 no session; 502 model error; 501 agent missing. Proxy re-checks the session id and caps
  figures at 30.

### 3.5 Readings CSV

- **UI:** "Readings CSV" link; `days=28` and `site_id` when station-scoped. **Chain:**
  `GET /api/live/studio/export/readings?days&site_id` → `officer.export_readings()`.
- **Data:** `_water()` (both water profiles) → `evaluate()` per row for threshold/factor/basis.
- **Output:** `text/csv` attachment, columns above, **deterministic**. **Failure:** upstream errors keep status.

### 3.6 Health-surveillance CSV

- **UI:** "Health CSV" link (hard-coded `days=90` in `studio.js`). **Chain:**
  `GET /api/live/studio/export/surveillance?days=90` → `officer.export_surveillance()`.
- **Data:** `_fetch(HEALTH_PROFILE, since=…)`. **Output:** `text/csv` with cases / population / rate / baseline.
- **Note:** district-wide — the proxy intentionally does **not** forward `site_id` for `surveillance`.

### 3.7 FHIR Bundle

- **UI:** "FHIR Bundle" link, **rendered only when `siteId` is set** (station scope). **Chain:**
  `GET /api/live/studio/export/fhir?days&site_id` → validates `site_id` (422 without) → `officer.export_bundle()`.
- **Data:** three profile queries for one station; entries `fullUrl = <base>/Observation/<id>`.
- **Output:** `application/fhir+json` collection Bundle, `meta.tag` dataset-scoped, deterministic.
- **Note:** collection Bundle is a *packaging* of station evidence — it is not a transaction and creates no
  new `Evidence` resource.

---

## 4. Existing-video coverage matrix

Runtime split of the current ≈4:18 cut (from `video/shot-list.md` scene timings):

| Phase | Scenes | Time | Share |
|---|---|---|---|
| Setup / scope | 0, 1 | 0:00–0:32 | ≈12 % |
| Evidence inspection | 2, 3, 4 | 0:32–1:38 | ≈26 % |
| Agent work | 5, 6, 7 | 1:38–3:08 | ≈35 % (but **fallback, not the agent**) |
| Ingestion provenance | 8 | 3:08–3:55 | ≈18 % |
| Operational handoff | 9 | 3:55–4:30 | ≈9 % (close only; **no artifact opened**) |

| Existing scene | Capability claimed | Actually shown on screen | Happens but remains hidden | Missing opportunity | Keep / shorten / replace |
|---|---|---|---|---|---|
| 0 Title | "two kinds of evidence" | Title card | — | — | **Keep** (0:08) |
| 1 Scope & mode | live FHIR, dataset tag | mode indicator, tag line | tag scopes every query | — | **Shorten** to ~0:15 |
| 2 Context | env + health at one Location | observations table | daily vs weekly cadence | — | **Keep**, trim |
| 3 Evidence | screening flag + basis | drawer, `FHIR_OBSERVATION` + `THRESHOLD_RULE` | `live-evidence-*` is derived | — | **Keep** |
| 4 Boundary | not causation | lower third | — | — | **Keep** (fold into 3) |
| 5 Open Studio | agent investigates | **fallback curl output** | the actual Streamed UI, scope selector | **agent choosing tools** | **Replace** |
| 6 Watch the work | tool trace, charts, grounding | charts only | streaming trace, FHIR queries, grounding chip | **grounding demonstrated** | **Replace** |
| 7 Honest label | descriptive offset, caveat | offset JSON | — | — | **Keep** (best in cut) |
| 8 Provenance | real pipeline, alert, mapping | pipeline run | identical code path | — | **Shorten** |
| 9 Convergence/close | one pipeline, boundaries | graphic + refresh | **all five handoff artifacts** | **the entire payoff** | **Replace** |

**Verdict:** the agent work occupies the largest share of runtime while showing the least of the system — it is
the only phase filmed against a fallback. The handoff, which is where the product's operational value lives, is
the smallest phase and shows no artifact.

---

## 5. Recommended new story

**One-sentence audience promise.**
*"Follow one real surveillance question from the moment an officer asks it to the moment it becomes five
different handoffs — and see exactly how far the evidence lets anyone go."*

**Narrative arc (the revised spine).**
An officer asks a real operational question → **the agent chooses the evidence and the analytical views** →
**the Studio shows its work** (tools and FHIR queries stream in) → **the system presents and numerically
checks the conclusion** → **the same investigation becomes handoffs for different recipients** →
**the officer can act without losing provenance or overstating causality.**

**Can it fit 3–5 minutes?** The current cut is ≈4:18. Two of its nine scenes (5, 6) must be *replaced* rather
than added to, and Scene 9 must be *replaced* by the handoff sequence. Reallocating existing time, the story
fits a **≈4:30 main cut** with a **short optional capability appendix**. I do **not** silently lengthen the
video: the revised scene table below stays ≤4:35 and lists explicit compressions.

### Revised scene table (main cut)

| # | Time | Screen action | Narration purpose | Exact capability demonstrated | Evidence source |
|---|---|---|---|---|---|
| 0 | 0:00–0:08 | Title card | Frame the promise (question → handoff) | — | `video/scene-cards` |
| 1 | 0:08–0:22 | `:8090/?mode=live`, station `yam-ito`, scope line | One investigation, one place, one tag | live FHIR scope | `live_overview` → `web.overview()` |
| 2 | 0:22–0:48 | Context tab: env row + health row | Two evidence streams, two cadences | station briefing | `/api/live/sites/yam-ito` |
| 3 | 0:48–1:08 | Evidence tab → drawer | Screening flag + quoted basis | `THRESHOLD_RULE` basis | `api.js liveFindings()`; `thresholds` |
| 4 | 1:08–1:30 | **Studio: type the question, scope = Current station, press Investigate** (live UI) | The agent works from intent | **`studio.run()` SSE + scope injection** | `studio.js run()`; `officer.studio_run()` |
| 5 | 1:30–2:05 | **Stream: reasoning → tool chips → expand one query → charts appear** | It chooses the evidence and the chart | tool selection + typed FHIR URLs + 2+ chart forms | `tool_done.urls`; `studio-charts.js` |
| 6 | 2:05–2:25 | **Answer + grounding chip; read `not_covered`** | The number check, and its limits | `grounding.check()` verdict | `grounding.py`; `test_studio.py` |
| 7 | 2:25–2:45 | Offset card (offset, `health_points`, caveat) | The honest label | `peak_offset()` caveat | `officer.peak_offset()` |
| 8 | 2:45–3:15 | **Handoff 1 — "how we reached it": open the Transcript** | Auditability for the record | self-contained transcript | `studio_report()` |
| 9 | 3:15–3:50 | **Handoff 2 — "what leaders need to decide": open the Executive report** | Decision-maker framing + the run's own charts | `studio_executive()` + embedded SVGs | `EXEC_PROMPT`; browser `figures[]` |
| 10 | 3:50–4:15 | **Handoff 3 — "what analysts and systems can reuse": open readings CSV, then health CSV side by side** | Two CSVs are *different* artifacts | `export_readings()` vs `export_surveillance()` | column sets verified live |
| 11 | 4:15–4:28 | **Open the FHIR Bundle** (`resourceType`, `type: collection`, `meta.tag`) | Interoperable, not a generic JSON | `export_bundle()` | verified live |
| 12 | 4:28–4:35 | Close + end card | Boundaries; act without overclaiming | — | `README`; caveats |

**Explicit compressions to stay ≤4:35:** fold Scene 4 (boundary card) into Scene 3's narration; shorten
ingestion provenance (old Scene 8) into a 15 s end-note or move it to the appendix — the *pipeline* is the
origin of the records but it is not the handoff story; drop the convergence graphic (old Scene 9) since the
artifact sequence now carries "one investigation → many outputs".

**Optional extended cut / appendix (≈60–90 s):** (a) ingestion provenance end-to-end (the old Scene 8, kept
intact); (b) `show_matrix`/`show_scatter`/`show_ranking` as a "different question, different chart" montage;
(c) `report_facts` shown as *ground truth the model cannot alter*; (d) the deterministic `curl` route showing
the same numbers without a model. This appendix is where the "feature-reel" material belongs — out of the main
cut.

---

## 6. Proposed narration changes

Only new or replaced blocks. Plain, concrete, scientifically careful.

**§6.1 — replaces the Scene 5/6 fallback narration**

> This time the officer doesn't click through stages. They ask a question, and the agent decides what to
> look at. Watch the panel: it says what it's about to do, then fetches the screening criteria *first* — so
> it never quotes a threshold from memory. Then it chooses its own tools. Which data to pull, which
> comparison to make, and — this is the part I want you to notice — *which chart answers the question*. A
> timeline here, a ranked list there. Those charts aren't sitting on a dashboard waiting; they're tools the
> model picked. Expand one and you can see the exact FHIR query it ran, with the URL on screen, so you could
> repeat it by hand. It never writes those URLs itself; it picks a checked tool and the code builds the
> query — because a made-up FHIR parameter returns an empty result that looks exactly like "no data."

**§6.2 — replaces the grounding sentence (new Scene 6)**

> Before you trust any of it: every number in that answer was checked, mechanically, against the data the
> tools actually returned. The green chip says six figures verified against a hundred and thirty-five
> retrieved. And then it tells you what that does *not* mean — read it — it checks numbers, not sentences. A
> figure that's really in the data can still be used in a wrong sentence, and a claim with no number in it —
> "levels are rising" — isn't checked at all. The software says so instead of letting the badge imply more
> than it proves.

**§6.3 — replaces the old Scene 9 close (the handoff block)**

> So the officer has an answer. But an answer isn't a handoff. Same run — five things out the other side.
>
> First, **how we reached it**: the transcript. The question, every step, every query, every figure, and the
> grounding verdict — attachable to an incident record so someone else can audit the route, not just the
> result.
>
> Second, **what leaders need to decide**: the executive report. Same evidence, rewritten as situation,
> findings, recommended action and limitations — with the actual charts from this run embedded, and a
> print-to-PDF page. A Chief Medical Officer who wasn't in the room can act on it.
>
> Third and fourth, **what analysts and systems can reuse**: two different CSVs. The readings file carries
> each reading with its criterion and basis. The surveillance file carries cases, rates and the population
> denominators behind them. Different recipients, different shapes — one file, retyped once, is how
> denominators get lost.
>
> And fifth, for interoperable systems: this isn't a generic JSON download. It's a tagged HL7 FHIR R4
> collection Bundle of the station's evidence, scoped to our dataset tag — the format an ABDM-aligned
> incident record can attach directly.
>
> Same investigation, one officer, no retyping — and every handoff keeps its provenance. Co-located records
> and a descriptive offset are a signal worth investigating; they are not causation. Confirmatory sampling
> is the next step, and that decision stays with the officer.

---

## 7. Recording plan and feasibility

Prerequisites for every live-model shot: **the gateway must have `OPENAI_API_KEY`** (it does — a full run
completed live while writing this), services on the right tag (`oah-demo-final`, verified), and the
dashboard at `:8090/?mode=live`.

| Shot | Page / route & click path | Prerequisites | Expected visual result | Live model call? | Deterministic fallback | ≈Duration | Risk & recovery |
|---|---|---|---|---|---|---|---|
| R4 Ask | dashboard → **Surveillance** nav → type prompt → **Investigate** (scope = Current station) | key; gateway up | composer clears, "Starting investigation…" → reasoning lines | **Yes** | record the deterministic `curl` route instead and narrate it as the same analyses | 0:20 | Model slow → warm the run once before filming; if it stalls, cut and re-issue the same question |
| R5 Stream | same panel, no clicks (expand one tool chip) | key; `MAX_ROUNDS` ≥ 4 | tool chips, one expanded to a `fhir_url`, ≥2 chart forms (trend + profile) | **Yes** | charts-only from `panels.py` rendered from the deterministic JSON | 0:35 | Nondeterministic tool choice → prompt with "show the trend at this station and the river profile"; keep the best take |
| R6 Grounding | answer card; hover/zoom the chip and `not_covered` | key | "✓ Grounded — n figures verified …" + the limitation line | Yes | show a pasted verdict JSON beside the chart | 0:20 | Chip may say "no figures to check" → ask a question that forces numbers; or show a captured verdict |
| R7 Offset | offset card **or** Terminal B `curl …/offset` | FHIR + tag; ≥14 d | `offset_days: 9`, `health_points: 4`, caveat | No | Terminal route | 0:20 | Always deterministic; safe |
| R8 Transcript | click **Transcript ↗** (new tab) | session alive | HTML with "Action 1..n", "Queries run", grounding chip | No | pre-capture one session's transcript | 0:30 | Session expired → re-run then immediately open the transcript |
| R9 Executive | click **Executive report**; it opens in a new tab | key; session alive | titled report, findings table, charts, actions, Verification | **Yes** | show `report_facts` JSON as the model-free alternative | 0:35 | Pop-up blocked → allow pop-ups; if model errors, narrate as a limitation |
| R10 CSVs | click **Readings CSV**, then **Health CSV** | FHIR + tag | two downloads; headers differ | No | deterministic | 0:25 | Browsers may auto-open CSV — download-then-open from the downloads bar for a clean shot |
| R11 FHIR | station scope → click **FHIR Bundle**; open in editor | station scope set | `resourceType Bundle`, `type collection`, `meta.tag oah-demo-final` | No | deterministic | 0:13 | Link is hidden in all-stations scope → ensure scope = Current station first |

**Recording risk to plan around:** the model-required shots (R4, R5, R9) are the only nondeterministic ones.
Warm them, keep two takes each, and always have the deterministic fallback framed as *"the same analyses,
computed without a model."*

---

## 8. Discrepancies and open questions

### 8.1 Verified defects / mismatches

1. **The current video's Studio scenes are a fallback, not the product.** `video/shot-list.md` says
   `OPENAI_API_KEY` is "NOT set" and directs Scenes 5–7 to `curl`. But the gateway *is* running with a key
   (a live run completed). Either the shot-list note is stale, or the recorder's shell lacks the key while
   the service has it. **Impact:** the video documents the agent yet shows a substitute.
2. **Live numbers have drifted from the plan's quoted values.** Today `river_profile` returns a largest step
   of **42.59× / 12 km** (means: Wazirabad 886.93 → ITO 37 775.21 → Okhla 32 294.29), whereas the plan §5 and
   shot-list quote **32.84×** with ITO 29 104 and Okhla 33 127. The seeded series is unchanged, so this is
   most likely a window/aggregation sensitivity (profile `days` default 14 vs 28) or a re-seed. **Action:**
   re-derive the on-screen numbers immediately before recording; do not reuse the plan's table.
3. **`Content-Disposition` mismatch for the executive report.** `studio_executive()` returns `HTMLResponse`
   with **no** attachment header, while every CSV/Bundle and the transcript *do* set one. The dashboard
   passes through only what upstream sends, so the proxy is correct. Minor, but the "download" affordance is
   inconsistent across the four handoffs.
4. **`README` route table uses a different prefix from what the dashboard calls.** README documents
   `/api/officer/…`; the dashboard proxy calls exactly that, and the standalone panel fetches
   `/api/officer/studio/run`. This is consistent — but the README shows `/api/officer/studio/run` returning
   SSE while the older bullet list (in the same README) lists `/api/officer/report` without a `panel` note.
   Documentation-only; no code defect.
5. **`test_routes.mjs` / `test_gateway_integration.py` are claimed in the tree but not exhaustively
   inspected here.** The `dashboard/tests/` directory contains `test_api.mjs`, `test_gateway_integration.py`,
   `test_routes.mjs`, `test_server.py`, `test_studio_proxy.py`, `test_studio_stream.mjs`; I verified behavior
   live rather than reading every test. **Open question:** whether the proxy test asserts the executive
   report's missing attachment header as intended.

### 8.2 Story / editorial choices (not defects)

6. **`co_located` means two different things.** Dashboard needs exceedance **and** `elevated_risk` (absent for
   India → never fires). Studio needs exceedance **and** ADD rise >15 % (fires for ITO). Both are honest; the
   story must not imply the dashboard tile corroborates the Studio. (The current plan already flags this.)
7. **The transcript footer calls the readings "synthetic demonstration data"** while Scene 6's narration and
   Scene 3's basis quote CPCB criteria. Both are true, but a viewer can hear "CPCB criterion" as
   "government data." The revised narration in §6.3 keeps the boundary explicit.
8. **`peak_offset` remains the strongest honesty beat** and should be kept verbatim; the revised story
   shortens it only to make room for the handoff, never cuts the caveat.
9. **The FHIR Bundle is station-only and collection-typed.** If the story says "attach to an incident," state
   that it is a *package of evidence* (collection), not a transaction, and that it creates no new resource.

---

## 9. Recommendation

**Must add to main cut**

1. **The real streamed Studio run** (Scene 4/5) — the agent choosing tools *and chart forms*, with one tool
   expanded to a visible FHIR URL. This is the capability the repository is built around and the current cut
   does not show.
2. **The grounding chip *and its `not_covered` text*** (Scene 6) — a demonstrated verification with its limit,
   not a claimed one.
3. **The handoff sequence** (Scenes 8–11): transcript → executive report → readings CSV → health CSV → FHIR
   Bundle, each tied to a recipient. This is the payoff and the reason the video is a workflow rather than a
   tour.
4. **The current-station vs all-stations contrast** — one line of narration over the scope selector; it is the
   difference between "this station" and "the district."

**Worth adding if time permits**

5. `report_facts` on screen as ground truth the model cannot alter.
6. A one-beat montage of `show_matrix`/`show_scatter` — "different question, different chart."
7. `get_site_profile` as the One Health join (chemistry beside population health in one call).

**Keep out of the main cut**

8. Ingestion provenance in full (compressed to a 15 s end-note or moved to the appendix).
9. The convergence graphic (the artifact sequence now carries the same idea).
10. All excluded/mock items (§2.9) — never opened on camera; stated in words in the close only.

**Approval gate.** Per the task instructions I have **not** generated or assembled a replacement video and
have **not** modified any application code, data, configuration, or existing video asset. On approval of the
story (§5) and narration (§6), the next step is to (a) re-derive the on-screen numbers from the *live* routes
to resolve the §8.1 drift, then (b) record per §7.
