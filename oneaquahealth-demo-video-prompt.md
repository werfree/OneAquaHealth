# Task: Regenerate the OneAquaHealth demo plan and final-video production prompt

Work only in this repository:

`/home/anindyasundar-bera/Projects/OneAquaHealth`

Your job is to produce two updated planning artifacts, in this order:

1. `oneaquahealth-demo-video-plan.md` — the evidence-backed story, storyboard, narration, and recording runbook.
2. `oneaquahealth-video-generation-prompt.md` — a self-contained production prompt that another coding-model session can use to record, assemble, verify, and deliver the final video from the approved plan.

Do not create or rebuild the final video in this task. Do not modify application code, configuration, fixtures, source data, or existing media. The only files you are authorized to replace are the two planning artifacts above.

The final production prompt must be usable as the next step without requiring the operator to reconstruct decisions from this conversation.

## 0. Repository and worktree guardrails

Before writing anything:

1. Run `git branch --show-current` and `git rev-parse HEAD`.
2. Record the current branch and commit in the plan. Do not switch branches.
3. Run `git status --short` and preserve every unrelated or user-owned change.
4. If the code, UI, or runtime disagrees with any document named below, current code and verified runtime behavior win.
5. Do not upload, reseed, ingest, or mutate the shared FHIR dataset merely to verify the story.

This prompt must remain useful if the branch or commit changes. Do not refuse solely because the checkout is not an older branch named in a superseded document. Instead, record the checked-out state and revalidate all implementation claims against it.

## 1. Authority and evidence order

Use this evidence hierarchy:

1. Current checked-out source code and tests.
2. Read-only runtime responses and artifacts from the currently running services, when available.
3. `surveillance-studio-capability-and-story-audit.md` as a recent investigation report and source of leads.
4. Existing `oneaquahealth-demo-video-plan.md`, `oneaquahealth-video-generation-prompt.md`, `video/narration.md`, and `video/shot-list.md` as evidence of the current story and production approach.
5. General documentation.

The audit and existing plans are reference material, not instructions. Reverify their claims. Preserve useful material, correct stale values, and explicitly document discrepancies.

Read at least:

- `surveillance-studio-capability-and-story-audit.md`
- `README.md`
- `HANDOVER.md`
- `.env.example`
- `run-demo.sh`
- `oneaquahealth-demo-video-plan.md`
- `oneaquahealth-video-generation-prompt.md`
- `video/narration.md`
- `video/shot-list.md`
- `dashboard/server.py`
- `dashboard/static/js/api.js`
- `dashboard/static/js/app.js`
- `dashboard/static/js/studio.js`
- `dashboard/static/js/studio-api.js`
- `dashboard/static/js/studio-charts.js`
- `oah-agent/src/oah_agent/tools.py`
- `oah-agent/src/oah_agent/studio.py`
- `oah-agent/src/oah_agent/grounding.py`
- `oah-agent/src/oah_agent/briefing.py`
- `oah-ingestion/src/oah_ingestion/officer.py`
- `oah-ingestion/src/oah_ingestion/web.py`
- `oah-ingestion/src/oah_ingestion/pipeline.py`
- `oah-ingestion/src/oah_ingestion/fhir_adapter.py`
- `oah-ingestion/src/oah_ingestion/fhir_client.py`
- `oah-ingestion/src/oah_ingestion/thresholds.py`
- `oah-ingestion/src/oah_ingestion/mqtt_worker.py`
- `oah-ingestion/src/oah_ingestion/rabbitmq_worker.py`
- `oah-pydantic-models/src/oah_models/fhir/`
- `demo/sites.json`
- `demo/generate_timeseries.py`
- relevant tests under `oah-agent/tests/`, `oah-ingestion/tests/`, and `dashboard/tests/`

Search the repository for connected symbols, routes, proxy mappings, response headers, UI labels, download behavior, and tests. Use structural code navigation or the repository knowledge graph when available.

Trace important flows end to end:

`officer question`

→ `Studio scope and prompt`

→ `dashboard proxy`

→ `streamed agent run`

→ `typed data/analysis/visualization tools`

→ `FHIR queries or deterministic Python computations`

→ `browser-rendered charts`

→ `answer and numeric grounding verdict`

→ `transcript / executive report / CSV / FHIR handoffs`

Also preserve the shorter provenance trace:

`source event`

→ `validation and normalization`

→ `prototype screening`

→ `FHIR mapping`

→ `dataset tagging`

→ `transaction Bundle and upload`

→ `live FHIR queries`

## 2. Story objective

The new video must show that Surveillance Studio is not merely a chat box or a dashboard. It is an auditable investigation workflow:

> One officer asks one operational question. The agent chooses which evidence, computation, and visual form answer it. The Studio shows its work, checks the figures in its conclusion, and turns the same investigation into handoffs for auditors, leaders, analysts, and interoperable systems.

Retain the strongest existing motif:

> One river, two kinds of evidence.

But change the payoff from “the data entered one pipeline” to:

> One investigation, five usable handoffs.

The handoffs to verify and make visible are:

1. **Investigation transcript** — how the conclusion was reached.
2. **Executive situation report** — what leaders need to decide, with findings, actions, limitations, verification, evidence queries, and the run's actual figures.
3. **Environmental readings CSV** — readings with their criterion, basis, exceedance factor, and source Observation id.
4. **Health-surveillance CSV** — cases, population denominators, rates, baselines, and source Observation id.
5. **Tagged FHIR R4 collection Bundle** — station evidence packaged for an interoperable system without retyping.

The narrative must remain a single bounded investigation, not become a download-button tour. Tie each artifact to a recipient and a job:

- auditor or incident record → transcript
- District Surveillance Officer / Chief Medical Officer → executive report
- analyst → purpose-specific CSVs
- ABDM-aligned or FHIR-capable system → FHIR Bundle

## 3. Runtime and format

Design a main video between **3:00 and 5:00**, targeting approximately **4:30**. The hard ceiling is **5:00**.

If all useful capabilities cannot fit, prioritize the investigation and handoff loop. Move secondary capabilities into an optional **60–90 second appendix**, rather than silently lengthening the main cut.

Recommended main-cut emphasis:

- approximately 20–25%: live context and evidence boundary
- approximately 35–40%: real streamed Studio investigation, tool choice, charts, and grounding
- approximately 30–35%: transcript, executive report, CSVs, and FHIR Bundle
- approximately 10%: concise provenance bridge and close

Do not spend the largest block of runtime on terminal output. The product UI and the produced artifacts should carry the story.

## 4. Primary demonstration setting

Prefer the synthetic Indian surveillance demonstration centered on Yamuna at ITO Bridge (`yam-ito`) if the current repository and runtime still support it.

Verify rather than assume:

- the current dataset tag
- the FHIR base URL
- the station name and id
- the available environmental and health observations
- the configured observation window
- current values, changes, thresholds, persistence, river-profile step, and peak offset
- the number of weekly health observations in the offset calculation
- the exact current UI labels

The time-series data and live aggregation can drift by date, window, or reseeding. Never copy a value from an older plan without querying it again immediately before finalizing the plan and again before recording.

The recent audit reported a specific river-profile discrepancy between the older plan and a later live response. Investigate it. The plan must explain which `days` window produced each number and prohibit reusing stale values.

## 5. Complete capability surface to verify

The following are leads, not permission to skip inspection.

### 5.1 Typed FHIR retrieval and context tools

Verify the schemas and behavior of:

- `get_thresholds`
- `list_sites`
- `search_observations`
- `get_site_profile`
- `get_cohort`

The story should clearly explain the most important safety property: the model selects a typed tool, while application code constructs the FHIR query. Do not imply that the model freely invents FHIR URLs.

### 5.2 Deterministic analytical tools

Verify:

- station trends and period comparisons
- ward prioritization
- river longitudinal profiles and largest monitored step
- exceedance persistence
- descriptive peak offset
- deterministic report facts

Establish precisely what each calculation means. For example, verify whether a “change” compares two halves of a window, two weeks, or another period. Do not narrate a stronger interpretation than the code computes.

### 5.3 Agent orchestration and visible work

Verify and plan to show:

- current-station versus all-stations scope
- model-selected data, analytical, and visualization tools
- server-sent streaming of start/planning, tool calls, results, renders, answer, completion, and errors
- visible tool arguments
- auditable FHIR evidence links
- the maximum tool-call round behavior
- session creation and in-memory lifetime

The real streamed Studio run is the centrepiece. A deterministic terminal fallback must never be edited to look as if it were the agent. If a model key is unavailable at production time, the production session must stop and report the blocker or use a clearly labelled alternate cut approved in the plan.

### 5.4 Visualization tools

Inventory and verify every render type, including:

- headline statistics
- station × indicator matrix
- ward ranking
- aligned environmental/health trend
- ward scatter comparison
- river profile
- persistence strip

The model's selection of a chart form is itself part of the product story. Prefer two or three meaningful visualizations over a montage of every chart.

### 5.5 Numeric grounding and auditability

Verify exactly how `grounding.check()` works and what is included in its evidence set.

The main cut must visibly show:

- the grounding chip or verdict
- how many figures were checked, if the run produces figures
- its `not_covered` or equivalent limitation text

Do not overstate grounding. If current code still behaves as reported, explain that it checks whether numeric literals are present in retrieved evidence; it does not prove that a supported number is used in the correct sentence, and it does not check number-free claims.

### 5.6 Investigation transcript

Inspect the actual artifact, not merely its button. Verify:

- source session requirements
- MIME type and filename
- question, streamed reasoning/narration, tool steps, arguments, evidence queries, returned figures, conclusion, and grounding verdict
- behavior after a process restart

Present the transcript as the audit trail: **how we reached the conclusion**.

### 5.7 Executive situation report

Inspect the actual artifact and verify:

- whether a model call is required
- how the transcript and captured chart SVGs are supplied
- report sections and grounding behavior
- evidence-query appendix
- response MIME type and download/open behavior
- print styling and browser Save as PDF

Do not call it a native PDF if the implementation returns print-ready HTML. Present it as the decision handoff: **what leaders need to decide**.

### 5.8 CSV and FHIR exports

Inspect actual response headers and contents for:

- readings CSV
- health-surveillance CSV
- station FHIR Bundle

Verify scope, time window, filenames, MIME types, columns, row counts, required parameters, resource types, Bundle type, dataset tag, and whether the output is deterministic.

Explain why the outputs are different:

- readings CSV retains measurements, screening basis, exceedance information, and source ids
- health CSV retains case counts, denominators, rates, and baselines
- FHIR export is a tagged `collection` Bundle of evidence, not a transaction Bundle and not a newly created FHIR `Evidence` resource

Present these as: **what analysts and systems can reuse**.

### 5.9 Ingestion and provenance

Verify MQTT, RabbitMQ, HTTP JSON, and HTTP CSV inputs and their shared pipeline. Retain this only as a concise provenance bridge in the main cut unless timing proves it earns more space.

The full ingestion walkthrough, source-channel comparison, deterministic resource ids, replay/upsert behavior, and transaction upload are strong candidates for the optional appendix.

Do not perform a write to a shared FHIR server solely for the video. If a recording needs a live write, require an isolated FHIR server or an explicitly approved, uniquely scoped dataset tag.

## 6. Required implementation classification

Classify every material capability using exactly one of:

- `LIVE — deterministic`
- `LIVE — model required`
- `LIVE — session-dependent`
- `LIVE WITH LIMITATIONS`
- `MOCK / SIMULATED`
- `NOT IMPLEMENTED`
- `UNVERIFIED`

For every capability, record:

- user value
- UI entry point
- route/proxy/function chain
- data source
- model-key dependency
- FHIR/dataset dependency
- read/write behavior
- station or district scope
- process/session lifetime
- visible limitation
- suitability for the main cut, appendix, or exclusion

At minimum classify:

- live overview and station detail
- dashboard-derived evidence references
- typed FHIR tools
- each deterministic officer analysis
- every chart/render type
- streamed Studio investigation
- current-station and all-stations scope
- numeric grounding
- Studio transcript
- executive situation report
- deterministic report facts
- readings CSV
- health-surveillance CSV
- FHIR Bundle export
- ingestion sample execution
- MQTT, RabbitMQ, HTTP JSON, and HTTP CSV ingestion
- FHIR mapping, transaction Bundle generation, upload, and tagging
- relationship graph
- mock report lifecycle
- durable run history and retry
- persona authorization
- production authentication
- causal or epidemiological inference

## 7. Truth boundaries that must survive every rewrite

### 7.1 Scientific boundary

The dataset is synthetic demonstration data. Never present it as observed CPCB, IDSP, IHIP, hospital, municipal, or state-board data.

Always preserve:

> Co-location, parallel movement, and a descriptive peak offset can identify a signal worth investigating. They do not establish attribution, exposure, correlation, or causation.

Never say or imply:

- the river caused illness
- the largest monitored step identifies a specific discharge
- the peak offset proves a lagged effect
- a screening reference is a legal determination
- the agent independently establishes scientific truth

Use language such as:

- “screened against the prototype reference”
- “the largest change appears between these monitored stations”
- “this narrows where confirmatory sampling may be useful”
- “a descriptive offset between maxima”
- “the available evidence does not establish attribution or causation”

### 7.2 FHIR and evidence boundary

Verify and preserve:

- dataset tags scope records on a shared FHIR server; they are not risk classes
- dashboard `live-evidence-*` identifiers are dashboard-level references unless current code proves otherwise
- underlying records may be FHIR `Observation`, `Group`, `Location`, and related resources
- the exported FHIR Bundle packages station evidence; it does not create a separate FHIR `Evidence` resource
- a collection Bundle is not a transaction Bundle

### 7.3 Live versus mock boundary

Never present these as live unless the current implementation has changed and runtime verification proves it:

- relationship graph
- mock dashboard report lifecycle
- durable ingestion-run history or retry
- persona UI as production authorization
- mock report downloads

Keep the live Studio transcript and executive report distinct from the mock dashboard's report feature.

### 7.4 Security and operational boundary

Verify and disclose relevant limitations:

- live gateway authentication status
- use of a shared HAPI FHIR sandbox
- FHIR availability and pagination limits
- overview and browser caching
- external broker dependencies
- Studio sessions held in memory and lost on restart
- model dependency for investigations and executive prose
- deterministic exports versus model-produced prose

## 8. Required narrative structure

Use this as the default main-cut spine and adjust only when verified implementation evidence supports a stronger version:

1. **Promise:** one river, two kinds of evidence, one operational question.
2. **Scope:** live mode, current dataset tag, Yamuna at ITO Bridge.
3. **Evidence:** environmental and health records associated with the same FHIR Location; screening basis visible.
4. **Question:** open Surveillance Studio in current-station scope and ask a focused operational question.
5. **Agent at work:** show streamed planning, tool calls, one expanded FHIR query, and two or three model-chosen charts.
6. **Honest answer:** show the numeric grounding verdict and its limitation; preserve the descriptive-offset caveat.
7. **Audit handoff:** open the transcript — “how we reached it.”
8. **Decision handoff:** open the executive report — “what leaders need to decide.”
9. **Reuse handoff:** distinguish readings CSV from health CSV — “what analysts can reuse.”
10. **Interoperability handoff:** open the tagged FHIR collection Bundle — “what systems can reuse.”
11. **Provenance bridge:** briefly connect these records to the shared ingestion/FHIR pipeline, or move the full walkthrough to the appendix.
12. **Close:** same investigation, no retyping, provenance retained, no causal overclaim.

The story must make the output artifacts visible. A row of download buttons is not sufficient: open the transcript, report, CSV headers, and key Bundle fields on screen.

The story must also make the agent visible. Terminal output from deterministic endpoints is a fallback or appendix, not a substitute for the Studio run.

## 9. Output A — `oneaquahealth-demo-video-plan.md`

Replace the existing plan with a complete, self-contained document containing these sections.

### 9.1 Verified baseline

State:

- branch, commit, and worktree status
- inspection date
- principal applications and ports
- FHIR base URL and dataset tag, if runtime-verified
- selected station and time window
- model availability as observed by the gateway, without exposing secrets
- whether runtime checks were read-only
- files and tests used as evidence

### 9.2 Executive narrative decision

Explain:

- the audience promise
- why this is one investigation rather than a feature tour
- why the handoff is the payoff
- what moved to the appendix and why

### 9.3 Implementation and truth map

Use:

| Capability | Classification | User value | Actual implementation path | Dependencies | Limitations | Main cut / appendix / exclude | Evidence |
|---|---|---|---|---|---|---|---|

### 9.4 Verified values and artifact contracts

Record values with:

- route and exact parameters
- retrieval timestamp
- result
- whether safe to hard-code or must be refreshed before recording

Also record artifact MIME type, filename, key columns/fields, scope, and session behavior. Do not freeze transient row counts or calculated values into narration unless they are rechecked during production.

### 9.5 Detailed main-cut storyboard

Use:

| Time | Scene | Screen / visual | Presenter action | Narration purpose | Technical event | Classification | Evidence |
|---|---|---|---|---|---|---|---|

Target approximately 4:30 and prove the total is below 5:00.

Every scene must name:

- exact URL or page
- selected station and scope
- tab/button/prompt
- expected visible UI state
- fields, chart, chip, query, or artifact section to highlight
- live/model/deterministic/session dependency
- fallback and whether it is allowed in the main cut

### 9.6 Optional appendix storyboard

Provide a separate 60–90 second appendix for valuable material that does not fit, such as:

- full ingestion provenance
- matrix/ranking/scatter comparison
- deterministic report facts
- model-free endpoint verification

Do not include the appendix in the main runtime total.

### 9.7 Complete presenter script

Write the full narration, scene by scene.

It must be:

- conversational and suitable for mixed technical/nontechnical viewers
- precise about typed tools, deterministic analyses, and model-produced prose
- explicit about synthetic data and association-not-causation
- clear about the different recipients for transcript, report, CSVs, and FHIR Bundle
- restrained enough to fit the timed scenes

Include concise language equivalent to:

- **Transcript:** “how we reached it.”
- **Executive report:** “what leaders need to decide.”
- **CSVs and FHIR:** “what analysts and systems can reuse.”

Do not copy changing numeric values into narration unless the plan marks them verified for production.

### 9.8 Recording runbook

Give an exact, repository-grounded sequence covering:

- service and dependency preflight
- verifying the gateway's effective model access, not merely the interactive shell environment
- read-only FHIR checks
- browser URLs and mode
- exact Studio scope and prompt
- how to obtain a run that visibly selects the intended tools without fabricating a result
- immediate transcript and report capture before session loss
- opening the two CSVs and FHIR Bundle cleanly on camera
- cache and refresh behavior
- terminal layout only where necessary
- media capture order
- reset/recovery steps
- when production must stop rather than substitute a misleading fallback

### 9.9 Demo risk checklist

Use:

| Risk | Why it matters | Preflight check | Mitigation / approved fallback |
|---|---|---|---|

Cover at least:

- model unavailable or nondeterministic tool choice
- Studio session loss
- executive-report failure
- FHIR availability and tag mismatch
- live value drift
- stale overview/browser cache
- shared-server contamination
- mock/live confusion
- artifact download/open behavior
- row-count drift
- missing observations
- accidental causal overstatement
- total-runtime overflow

### 9.10 Visual and editorial plan

Keep product interfaces and real artifacts central. Specify only the minimum supporting graphics needed, such as:

- opening title
- a restrained recipient/handoff overlay
- concise provenance bridge
- boundary/end card

Do not generate fake product UI or fake reports. Use real recordings and actual downloaded artifacts.

### 9.11 Demo truth matrix

Use:

| Demo claim | Classification | Code/runtime evidence | Safe narration | On-screen proof |
|---|---|---|---|---|

Include every material narration claim.

### 9.12 Acceptance criteria

Define pass/fail checks for:

- runtime between 3:00 and 5:00
- real live Studio run shown
- at least one tool's arguments and FHIR evidence URL shown
- at least two model-selected visual forms shown
- grounding verdict and limitation visible
- transcript opened
- executive report opened with actual run figures
- readings CSV and health CSV visibly distinguished
- FHIR `Bundle`, `type: collection`, and dataset tag visible
- no mock-only capability presented as live
- synthetic-data and scientific boundaries spoken and visible
- no stale number used
- no generated product UI

## 10. Output B — `oneaquahealth-video-generation-prompt.md`

After the plan is complete, replace the existing production prompt with a self-contained prompt for a new coding-model session that will create the final video.

The production prompt must:

1. Name `oneaquahealth-demo-video-plan.md` as the authoritative editorial plan while still requiring code/runtime revalidation.
2. Re-state all scientific, FHIR, live/mock, and model-dependency boundaries needed for safe production.
3. Require a read-only preflight before any media is generated.
4. Require a real streamed Studio session in the main cut. If model access is unavailable, stop and report rather than silently replacing the agent with terminal output.
5. Require transcript and executive-report capture before the gateway restarts because the session is in memory.
6. Require actual inspection and recording of both CSVs and the FHIR Bundle.
7. Require current live values to be re-derived immediately before recording.
8. Restrict writes to production assets under `video/` or the existing approved video-production workspace. Do not modify application code, source data, fixtures, or configuration.
9. Preserve user-owned existing media; replace only the outputs explicitly named in the production plan.
10. Require real screen recordings for product UI, charts, transcript, report, CSV, terminal, and FHIR views. Generated graphics may be used only for title cards, boundary cards, the concise provenance bridge, and the end card.
11. Produce captions and narration synchronized to the final edit.
12. Verify the assembled video visually and technically before delivery.

At minimum, the production prompt must request these deliverables:

- final narration source
- timed subtitle file
- final shot/recording checklist
- any required title, boundary, provenance, handoff, and end-card assets
- recorded/captured scene media or explicit placeholders when capture is impossible
- assembly project/script using the repository's established video tooling
- final video file
- thumbnail
- a verification report containing exact duration, resolution, audio/caption status, scene provenance, live/model/deterministic classification, and any deviation from the plan

The production prompt must include hard stop conditions:

- wrong dataset tag or missing story station
- no usable environmental/health data for the selected window
- unavailable model access for the real Studio scene
- Studio run without a session id
- transcript/report no longer accessible
- grounding failure or unsupported figures that would appear in narration
- artifact response does not match the expected MIME/schema
- mock mode visible in a scene presented as live
- final runtime above 5:00

It must also require proportional fallbacks:

- retry or recapture a nondeterministic Studio run using the same truthful question
- use deterministic routes only for verification, appendix material, or an explicitly labelled alternate shot
- re-record after refreshing stale data
- omit a capability rather than inventing a successful result

## 11. Final consistency pass

Before returning:

1. Compare the plan and production prompt side by side.
2. Confirm their scene order, runtime, URLs, prompts, station, artifact names, boundaries, and acceptance criteria agree.
3. Confirm neither document instructs the production session to show mock-only behavior as live.
4. Confirm the production prompt can be pasted into a fresh coding-model session and executed without this conversation.
5. Confirm only the two authorized files changed.

Return:

- a concise summary of the redesigned story
- links to both updated files
- the verified branch and commit
- the target main-cut runtime
- any unresolved discrepancy that the production session must recheck

Do not begin final-video production in this task.
