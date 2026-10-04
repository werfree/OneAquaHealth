# Prompt — investigate Surveillance Studio and reframe the demo story

> Copy everything below the divider into a new coding-model task opened at
> `/home/anindyasundar-bera/Projects/OneAquaHealth`.

---

You are a senior product engineer, technical investigator, and demo-story editor working inside the OneAquaHealth repository.

Your task is to discover the complete, currently implemented capability surface of the agents and the District Surveillance Officer Studio, determine what the existing demo video does and does not communicate, and then recommend a stronger story that makes the hidden work visible.

This is an evidence-led investigation. Treat the current source code and, when available, the running live services as authoritative. Existing plans and narration are evidence of what the video currently claims, but they are not proof of runtime behavior.

Do not modify application code, data, configuration, or existing video assets during this task. Do not generate or assemble a replacement video yet. First produce a capability audit and a proposed story revision for approval.

## Goal

The present video shows part of a Studio investigation, but much of the system's value happens behind the interface or after the answer appears. Make that work legible.

Investigate at least these questions:

1. What can the agent actually decide, call, compute, visualize, verify, stream, and export?
2. What does the user see during a Studio run, and what important behavior remains visually hidden?
3. Which artifacts can the Studio produce after an investigation—for example an audit transcript, an executive situation report, environmental readings CSV, health-surveillance CSV, and a FHIR evidence Bundle?
4. How are those artifacts grounded in the investigation and source FHIR records?
5. Which features are deterministic, which require a model/API key, which depend on live FHIR data, and which are mock-only or not implemented?
6. Which capabilities appear in the current video, which are mentioned but not shown, and which are absent?
7. How should the story be reframed so the audience sees an end-to-end operational workflow rather than a dashboard tour or a list of features?

## Evidence to inspect

Begin by reading these files in full:

- `README.md`
- `oneaquahealth-demo-video-plan.md`
- `oneaquahealth-demo-video-prompt.md`
- `oneaquahealth-video-generation-prompt.md`
- `video/narration.md`
- `video/shot-list.md`
- `oah-agent/src/oah_agent/studio.py`
- `oah-agent/src/oah_agent/tools.py`
- `oah-agent/src/oah_agent/grounding.py`
- `oah-agent/src/oah_agent/assistant.py`
- `oah-ingestion/src/oah_ingestion/officer.py`
- `oah-ingestion/src/oah_ingestion/web.py`
- `dashboard/static/js/studio.js`
- `dashboard/static/js/studio-api.js`
- `dashboard/static/js/studio-charts.js`
- `dashboard/server.py`

Then search the rest of the repository for related routes, proxy mappings, UI controls, tests, fixtures, report generation, download behavior, FHIR queries, dataset scoping, and safety/grounding checks. Do not assume the list above is exhaustive.

Use structural code navigation or the codebase graph when available. Trace important capabilities end to end:

`user action` → `dashboard UI` → `dashboard proxy` → `gateway route` → `agent/tool` → `FHIR query or computation` → `streamed event/rendered chart` → `grounding check` → `downloaded artifact`

For every claim, cite the supporting file, symbol or route, and relevant line number where practical.

## Capability hypotheses to verify, not blindly repeat

The repository appears to expose both data-retrieval tools and analytical/visualization tools. Verify the exact schemas, behavior, inputs, outputs, and limitations of all of them.

Likely retrieval/context tools include:

- `get_thresholds`
- `list_sites`
- `search_observations`
- `get_site_profile`
- `get_cohort`

Likely analysis and presentation tools include:

- `rank_wards`
- `get_trend`
- `show_stats`
- `show_matrix`
- `show_ranking`
- `show_trend`
- `show_scatter`
- `show_river_profile`
- `show_persistence`
- `peak_offset`

Likely investigation/output capabilities include:

- server-sent streaming of planning, tool starts, tool results, charts, answers, and completion/error events
- typed tool calls that construct FHIR queries rather than allowing the model to invent query URLs
- visible FHIR evidence links and tool arguments
- numeric grounding that compares figures in the final answer against retrieved tool results
- in-memory investigation sessions
- downloadable HTML investigation transcripts containing the question, reasoning/narration, tool calls, queries, returned figures, conclusion, and grounding verdict
- model-generated executive situation reports based on the transcript and captured chart SVGs
- print/save-to-PDF behavior for the executive report
- deterministic report facts
- environmental readings CSV export
- health-surveillance CSV export preserving cases, rates, and population denominators
- a tagged FHIR R4 collection Bundle of station evidence

Verify each item. Discover anything missing from this list.

## Live verification

If the local services are already running, perform read-only checks against their health, information, Studio, analysis, report-facts, and export endpoints. You may run a new Studio investigation only if the required model key is already configured and doing so does not modify source data. Do not ingest, seed, upload, or alter data in this task.

If services are unavailable, continue with static code and test evidence. Clearly label anything not runtime-verified. Do not start services or change configuration merely to make the audit look complete.

For downloads, inspect response headers, MIME types, filenames, schemas/columns, FHIR Bundle type and contents, dataset tags, and whether the artifact is generated deterministically or by a model. Do not describe an HTML file as a native PDF; state that it is print-ready HTML with browser Save as PDF if that is what the code implements.

## Required classification

Classify every capability as exactly one of:

- `LIVE — deterministic`
- `LIVE — model required`
- `LIVE — session-dependent`
- `LIVE WITH LIMITATIONS`
- `MOCK / SIMULATED`
- `NOT IMPLEMENTED`
- `UNVERIFIED`

Also record dependencies and constraints, including:

- whether `OPENAI_API_KEY` is required
- whether a reachable FHIR server and correct dataset tag are required
- whether state disappears on process restart
- whether the capability is station-scoped or district-wide
- whether it reads data, writes data, or only formats existing results
- whether it is directly visible in the UI
- whether it is suitable for the live demo

Preserve the project's truth boundaries:

- synthetic demonstration data must never be presented as observed government or clinical data
- screening references are prototype criteria, not statutory enforcement limits
- co-location, trends, and peak offsets do not establish attribution or causation
- the peak offset is descriptive, not a correlation, and its small number of weekly health observations must remain visible
- numeric grounding checks whether figures are present in retrieved evidence; verify and state what it does not prove
- dashboard `live-evidence-*` identifiers are dashboard-level references unless the code proves they are stored FHIR `Evidence` resources
- live Studio/report behavior must not be confused with the separate mock dashboard report lifecycle, mock relationship graph, mock ingestion history, or simulated persona controls

## Compare against the existing video

Build a coverage matrix for every existing scene in `video/narration.md` and `video/shot-list.md`:

| Existing scene | Capability claimed | Actually shown on screen | Happens but remains hidden | Missing opportunity | Keep / shorten / replace |
|---|---|---|---|---|---|

Pay special attention to whether the current cut visibly demonstrates:

- the model selecting tools and chart forms based on the question
- the distinction between data tools, analytical computations, and visualization tools
- the streamed tool trace and auditable FHIR queries
- numeric grounding and its limitations
- the difference between current-station and all-stations investigations
- the complete post-investigation artifact workflow
- how a transcript differs from an executive report
- how the two CSV exports differ from one another
- why the FHIR Bundle is more than a generic JSON download
- how an officer could hand evidence to different downstream audiences without retyping it

Do not recommend showing every capability at equal depth. Identify the few moments that make the broader capability set understandable.

## Story-design requirement

The revised story must remain a coherent investigation, not become a feature reel.

Use this candidate narrative spine as a hypothesis and improve it if the evidence supports a better one:

`An officer asks a real operational question`

→ `the agent chooses the evidence and analytical views`

→ `the Studio shows its work as tools and FHIR queries run`

→ `the system presents and numerically checks the conclusion`

→ `the same investigation becomes three kinds of handoff`

1. `Transcript` — for auditability: how the conclusion was reached
2. `Executive report` — for decision-makers: findings, actions, limitations, figures, and evidence appendix
3. `Data/FHIR exports` — for analysts and interoperable systems: readings CSV, health CSV, and tagged FHIR Bundle

→ `the officer can act without losing provenance or overstating causality`

Assess whether this can fit the current 3–5 minute constraint. If it cannot, propose the cleanest structure, such as a 4:30 main cut plus a short capability appendix, and explain the trade-off. Do not silently lengthen the video.

## Deliverables

Create one new file only:

`surveillance-studio-capability-and-story-audit.md`

It must contain:

### 1. Executive finding

A concise explanation of what the system truly does, what the current video under-communicates, and the single most important narrative change.

### 2. Complete capability inventory

A table with:

| Capability | Classification | User value | Implementation path | Visible today? | Dependencies | Limitations | Demo recommendation |
|---|---|---|---|---|---|---|---|

Group capabilities under:

- data retrieval and context
- analytical computation
- agent orchestration
- visual explanation
- grounding and auditability
- reports and handoffs
- CSV/FHIR interoperability
- ingestion/provenance that directly supports the Studio story

### 3. End-to-end traces

Trace at least these workflows:

- one current-station investigation
- one all-stations comparison
- transcript generation
- executive-report generation
- readings CSV
- health CSV
- FHIR Bundle

For each, show the UI action, route/proxy chain, core functions, data source, output, and failure/session behavior.

### 4. Existing-video coverage matrix

Use the requested scene-by-scene format. Quantify how much of the current runtime is spent on setup, evidence inspection, agent work, ingestion provenance, and operational handoff.

### 5. Recommended new story

Provide:

- a one-sentence audience promise
- the narrative arc
- a revised scene table with timestamps, screen action, narration purpose, exact capability demonstrated, and evidence source
- explicit cuts or compressions needed to stay under five minutes
- one optional extended-cut or appendix idea for capabilities that do not fit

The recommendation should make the post-investigation handoff visible. A strong default is to show the completed run transforming into the transcript, executive report, both CSVs, and the FHIR Bundle through a short, purposeful sequence tied to different recipients—not a row of unexplained download buttons.

### 6. Proposed narration changes

Write only the new or replaced narration blocks, not a full rewrite. Keep the language plain, concrete, and scientifically careful. Include a short line that distinguishes:

- “how we reached it” — transcript
- “what leaders need to decide” — executive report
- “what analysts and systems can reuse” — CSV and FHIR exports

### 7. Recording plan and feasibility

For each proposed new shot, specify:

- exact page/route and click path
- prerequisites
- expected visual result
- whether it needs a live model call
- deterministic fallback
- approximate duration
- recording risk and recovery plan

### 8. Discrepancies and open questions

List disagreements among code, docs, existing narration, and runtime evidence. Separate verified defects from story/editorial choices.

### 9. Recommendation

End with a prioritized decision list:

- `Must add to main cut`
- `Worth adding if time permits`
- `Keep out of the main cut`

## Quality bar

The audit is complete only if:

- every capability claim has code or runtime evidence
- every Studio tool and officer route has been accounted for
- model-required and deterministic behavior are clearly separated
- report, transcript, CSV, and FHIR outputs are inspected as actual artifacts, not inferred from button labels
- mock-only behavior is excluded from the live story
- the revised story fits its stated runtime
- the result explains the product's operational value, not merely its technical architecture

Return a short summary of your most important findings and a link to `surveillance-studio-capability-and-story-audit.md`. Do not begin implementing the revised video until I approve the story.
