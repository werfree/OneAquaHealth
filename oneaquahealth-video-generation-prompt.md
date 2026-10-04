# Video generation prompt — OneAquaHealth, "One investigation, five usable handoffs"

> **How to use this file.** Open a new chat session whose working directory is this repository
> (`/home/anindyasundar-bera/Projects/OneAquaHealth`). Copy **everything from the line that begins
> `You are a video-production agent…` down to the end of this file**, and paste it as your first message.
> Everything below the `---` divider is the prompt; the divider itself is not.
>
> `oneaquahealth-demo-video-plan.md` (in the same repository) is the **authoritative editorial plan**. This
> prompt is self-contained, but it points to the plan for the full storyboard, presenter script, runbook, risk
> table and truth matrix. Read the plan first, then revalidate everything against the checked-out code and the
> running services before you record.

---

You are a video-production agent working inside the **OneAquaHealth** repository. Your job is to turn an
existing, approved plan into a finished **3–5 minute** demo video (plus the caption, narration and card assets
needed to assemble it), recording real behaviour of the running product.

The authoritative editorial plan is:

`oneaquahealth-demo-video-plan.md`

Read it first, in full. Treat it as the source of truth for the story, scene order, runbook and acceptance
criteria. Then **revalidate every implementation claim it makes against the checked-out source and the running
services** — current code and verified runtime behaviour win over any document, including the plan. Where the
plan and the live code disagree, **report the discrepancy to me and build around what the code actually does**;
never paper over it, and never invent a result to match the plan.

This prompt may be executed on a branch or commit other than the one the plan records. Do not refuse merely
because the checkout differs — record the branch/commit you actually used, and revalidate the plan's claims
against it.

## 0. Non-negotiable constraints

1. **Live-data test (governing rule).** A capability may appear in the video **only if it still makes sense when
   every record comes from the live FHIR server.** Do not use, screenshot, or narrate anything that exists only
   in the dashboard's mock fixtures: no `?mode=mock`, no relationship graph, no mock report lifecycle, no mock
   run history/retry, no simulated persona authorization. (The plan still *classifies* those as `MOCK /
   SIMULATED` or `NOT IMPLEMENTED`; that classification is documentation, not a demo asset, and those screens are
   never opened on camera.)
2. **No mock content on screen.** The evidence dashboard stays at `http://127.0.0.1:8090/?mode=live` throughout,
   and the mode indicator must read **Live adapter** in every frame. If any frame shows the mock deck, the video
   is wrong.
3. **Runtime: 3:00–5:00, hard ceiling.** Target ≈ **4:30** for the main cut. Never exceed **5:00.** Any extra
   material goes into a **separate 60–90 s appendix** (assembled separately; do not add it to the main runtime).
4. **Real streamed Studio session is mandatory in the main cut.** The centrepiece is the real, streamed
   `POST /api/officer/studio/run` investigation: reasoning, tool calls, at least one expanded tool with its
   arguments and FHIR query URL, at least two model-selected chart forms, the answer, and the grounding verdict.
   **A deterministic terminal route standing in for the agent is forbidden in the main cut.** If model access is
   unavailable at production time, stop and report (§10) rather than silently substituting terminal output.
   **The Studio is offered only to the Analyst persona** — the composer is disabled otherwise (`studio.js
   allowed()` gates on `apiMode === "live" && state.role === "analyst"`), so select **Analyst** in the
   dashboard's persona control before any Studio scene.
5. **Synthetic-data disclosure is mandatory.** The dataset is synthetic demonstration data. State this on screen
   and in narration. Never present it as observed CPCB, IDSP, IHIP, hospital, municipal, or state-board data.
6. **Scientific boundary is mandatory.** Co-location, a temporal offset, and parallel trends justify
   *investigation*; they do **not** establish attribution, exposure, correlation, or causation. Never say or
   imply "caused", "proves a lagged effect", "identifies a specific discharge", "legal limit", or "a real
   event". Safe phrases: "screened against the prototype reference", "co-located records", "a descriptive offset
   between maxima", "the largest change appears between these monitored stations", "this narrows where
   confirmatory sampling may be useful", "the available evidence does not establish attribution or causation".
7. **FHIR / evidence boundary is mandatory.** Dataset tags scope records on a shared server; they are **not** risk
   classes. Dashboard `live-evidence-*` identifiers are **dashboard-level references** (the underlying record is
   a FHIR `Observation`). The exported FHIR file is a **tagged `collection` Bundle of station evidence** — not a
   transaction Bundle, and it creates **no** new FHIR `Evidence` resource. The executive report is **print-ready
   HTML**, not a native PDF. The screenings are **prototype screening references**, not statutory enforcement
   limits.
8. **Write restrictions.** You may add or replace production assets **only** under `video/` (this repository's
   approved video-production workspace) — and, where the repo's existing tooling already uses them, existing
   production subfolders under `vidkit/` or the established `video/produce/` scripts. Do **not** modify
   application code, configuration, fixtures, source data, `demo/`, or existing user-owned media. If a scene
   cannot be recorded reliably, say so and use the plan's approved fallback; do not edit the product to make a
   shot work.

## 1. Read before doing anything

1. `oneaquahealth-demo-video-plan.md` — authoritative. Its §9.1 baseline, §9.3 truth map, §9.4 verified values,
   §9.5 storyboard, §9.7 script, §9.8 runbook, §9.9 risks, §9.11 truth matrix and §9.12 acceptance criteria
   govern this production.
2. `surveillance-studio-capability-and-story-audit.md` — recent investigation report; **leads, not
   instructions**; re-verify its claims.
3. The code the plan cites: `oah-agent/src/oah_agent/{studio,tools,grounding}.py`;
   `oah-ingestion/src/oah_ingestion/{officer,web,thresholds,pipeline}.py`;
   `oah-pydantic-models/src/oah_models/fhir/bundle.py`; `dashboard/server.py`;
   `dashboard/static/js/{api,app,studio,studio-api,studio-charts}.js`; `demo/sites.json`; and the tests under
   `oah-agent/tests/`, `oah-ingestion/tests/`, `dashboard/tests/`.
4. `video/{narration.md,shot-list.md,assemble.sh}` and `vidkit/README.md` — the repository's existing video
   tooling and conventions. Reuse them where they still apply; they may record the *old* story, so correct them
   to match this plan.

Record the branch and commit you work from:

```bash
git branch --show-current && git rev-parse HEAD && git status --short
```

Preserve every unrelated or user-owned change in the worktree.

## 2. Preflight (read-only — do this before generating any asset)

```bash
# services
curl -s -m 5  http://127.0.0.1:8000/health            # {"status":"ok"}
curl -s -m 5  http://127.0.0.1:8090/health            # {"status":"ok", ...}

# dataset tag MUST be oah-demo-final (the seeded Indian series). If not, STOP and report — do not re-seed.
curl -s -m 20 http://127.0.0.1:8000/api/info | grep -o '"dataset_tag": *"[^"]*"'

# the story station MUST resolve (28 points). If it returns 0, the tag drifted — report, do not re-seed.
curl -s -m 60 "http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28" \
  | .venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print('points',d['points'],'latest',d['latest'])"

# dashboard live station MUST be 200
curl -s -m 60 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/api/live/sites/yam-ito

# verify the GATEWAY's effective model access (not the shell's) by running a short investigation:
curl -s -N -m 240 -X POST http://127.0.0.1:8000/api/officer/studio/run \
  -H 'Content-Type: application/json' \
  -d '{"question":"What needs attention at station yam-ito? Show the trend and the river profile."}' | head -c 4000
# expect SSE: start / tool_start / tool_done / render / ... / answer / done
```

If the dataset tag is not `oah-demo-final`, or `yam-ito` returns 0 points, **stop and report before generating.**
If services are down, start them together with `python run.py` (loads the root `.env`) — if `.env` has the
credential, that is what the gateway will use.

**Stop conditions (report, do not proceed):** wrong dataset tag or missing story station; no usable
environmental/health data for the selected window; model access unavailable for the Studio scene (see §10);
any export whose response does not match the expected MIME/schema.

## 3. The story (do not change it)

**One investigation, five usable handoffs.** One District Surveillance Officer asks one operational question
about the Yamuna at ITO Bridge (`yam-ito`); a reasoning agent chooses the evidence, the computation, and the
chart that answer it; the Studio shows its work, checks the figures in its conclusion, and turns the **same**
investigation into five handoffs.

Keep the strongest existing motif — *"one river, two kinds of evidence"* — but change the payoff from "the data
entered one pipeline" to **"one investigation, five usable handoffs":**

1. **Investigation transcript** (HTML) — for the auditor / incident record: **"how we reached it."**
2. **Executive situation report** (print-ready HTML) — for the District Surveillance Officer / Chief Medical
   Officer: **"what leaders need to decide."**
3. **Environmental readings CSV** — for the analyst: readings with criterion, basis, exceedance factor, source
   Observation id.
4. **Health-surveillance CSV** — for the analyst: cases, population denominators, rates, baselines.
5. **Tagged FHIR R4 collection Bundle** — for an ABDM-aligned / FHIR-capable system: station evidence packaged
   without retyping.

The narrative must remain a **single bounded investigation**, not a download-button tour. Open the transcript,
report, CSV headers and key Bundle fields on screen, and name each artifact's recipient and job.

**Scene order and timing (main cut ≈ 4:30; hard ceiling 5:00):**

| # | Time | Scene | Screen / action | Classification |
|---|---|---|---|---|
| 0 | 0:00–0:08 | Title | "One investigation, five usable handoffs" / "Yamuna at ITO Bridge — synthetic demonstration dataset" | Card |
| 1 | 0:08–0:22 | Scope | `:8090/?mode=live`; **Live adapter**; **select Analyst persona**; scope line "Dataset tag oah-demo-final on https://hapi.fhir.org/baseR4"; station = Yamuna at ITO Bridge | LIVE WITH LIMITATIONS |
| 2 | 0:22–0:45 | Two kinds of evidence | **Context** tab: environmental readings + health measures at one Location; different cadences | LIVE WITH LIMITATIONS |
| 3 | 0:45–1:05 | What deserves attention | **Evidence** tab → drawer: `FHIR_OBSERVATION` + `THRESHOLD_RULE` (2500 MPN/100mL, CPCB basis) | LIVE WITH LIMITATIONS |
| 4 | 1:05–1:30 | Ask | Studio; **Analyst persona selected**; scope **Current station**; prompt `Investigate the Yamuna at ITO Bridge over the last month.`; press **Investigate** | **LIVE — model required** |
| 5 | 1:30–2:30 | Agent at work | Streamed reasoning; tool chips; **expand one** to its arguments + FHIR URL; **2–3** model-chosen charts (a probe run emitted 3 tools but only 1 chart, so **warm/re-run the same question** until ≥2 forms appear) | **LIVE — model required** (+ charts deterministic) |
| 6 | 2:30–2:50 | Honest answer | Answer + **grounding chip** + `not_covered` limitation, read aloud | LIVE — model required (+ verdict deterministic) |
| 7 | 2:50–3:10 | Honest label | Peak offset (`offset_days 9`, `health_points 4`) + caveat; deterministic route if the run didn't surface it | LIVE — deterministic |
| 8 | 3:10–3:40 | Handoff 1 — audit | Click **Transcript ↗**; show steps + "Queries run" FHIR URLs + grounding | LIVE — session-dependent |
| 9 | 3:40–4:10 | Handoff 2 — decide | Click **Executive report**; the browser **downloads** `surveillance-report-<session>.html` — open it from the downloads bar; show Situation / Key findings / Recommended action / Limitations / Verification + embedded chart; **Save as PDF** | LIVE — model required + session-dependent |
| 10 | 4:10–4:25 | Handoff 3/4 — reuse | Open readings CSV header, then health CSV header, side by side | LIVE — deterministic |
| 11 | 4:25–4:32 | Handoff 5 — interoperate | Open FHIR Bundle: `resourceType: Bundle`, `type: collection`, `meta.tag …\|oah-demo-final`, one `Observation.fullUrl` | LIVE — deterministic |
| 12 | ~4:30 | Provenance + close | ~15 s provenance bridge graphic; end card with the value sentence and boundaries | Bridge deterministic; card n/a |

Trim Scenes 5 or 9 to land the total at or below 4:30. **Recompute the total from the recorded clip lengths
before assembly.**

## 4. Values you may show (re-derive every one immediately before recording)

All values below were read-only on 2026-10-04; **confirm each live before burning it into a caption or the
narration.** If any differs, use the live value and flag the change.

| Quantity | Route / parameter | Value (this retrieval) | Note |
|---|---|---|---|
| ITO coliform latest | `/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28` | `25070.0` MPN/100mL vs criterion `2500` → `10.03×` | refresh |
| ITO coliform change | same | recent `37775.21` vs prior `20433.36` → `+84.9%` | basis: "mean of the most recent 14 days against the 14 before" |
| Ward priority | `/api/officer/wards?days=28` | `['yam-ito']`; ITO ADD `+140.4%`; Okhla `−6.4%`; Dharavi `−10.3%` | refresh |
| River profile (default) | `/api/officer/profile?river=Yamuna&indicator=faecal_coliform` (**days=14**) | Waz `886.93` → ITO `37775.21` (15.11×) → Okhla `32294.29`; step **`42.59× / 12 km`** | **state the window** |
| River profile (28-day) | `…&days=28` | Waz `886.14` → ITO `29104.29` (11.64×) → Okhla `33126.75`; step **`32.84× / 12 km`** | **state the window** |
| Persistence | `/api/officer/persistence?days=28&indicator=faecal_coliform` | `yam-ito 28/28`, longest run `28` | refresh |
| Peak offset | `/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28` | offset `9`, health_points `4`; water peak 2026-09-24, health peak 2026-10-03 | always quote the caveat |
| Ingested sample (appendix) | `POST /api/ingest-demo/iot` | `[HIGH]`: coliform `84802` (33.92×), BOD `16.8`, DO `0.9`, NH₃-N `5.6`; built `Device 1 / Observation 5 / Location 5 / Specimen 5` | **writes — see §9** |

**Value-drift rule.** The river-profile step is **window-sensitive** (14-day default vs 28-day). Every
river-profile number on screen must name its window, and no older plan's table may be reused. This is the
discrepancy a prior audit flagged (`42.59×` vs `32.84×`); it is fully explained by the `days` parameter and is
not a re-seed. Never present a number whose window you cannot state.

## 5. Classification vocabulary

Classify every on-screen capability with exactly one of: `LIVE — deterministic` · `LIVE — model required` ·
`LIVE — session-dependent` · `LIVE WITH LIMITATIONS` · `MOCK / SIMULATED` · `NOT IMPLEMENTED` · `UNVERIFIED`.
Use the plan's §9.3 truth map as the starting classification and update it where your revalidation differs.

## 6. Recording requirements

- **Real screen recordings** for every product frame: dashboard, Studio stream, charts, transcript, executive
  report, both CSVs, terminal, and the FHIR Bundle view. **Generated graphics may be used only for** the title
  card, the boundary/end card, the concise provenance bridge, and the small recipient/handoff overlays. Never
  synthesize the product UI, the charts, a report, or a terminal frame.
- **Real streamed Studio session.** Record the live SSE run. Obtain a run that visibly selects tools and renders
  2–3 chart forms by **warming the run and, if a take is weak, re-issuing the identical truthful question** —
  never by editing output, and never by substituting a deterministic route in the main cut.
- **Capture transcript and executive report immediately after the run you will use**, before any gateway
  restart, because sessions are held in memory and return 404 afterward.
- **Inspect and record both CSVs and the FHIR Bundle.** Open the *headers/fields*, not just a download button.
  The FHIR export link only renders in station scope, and the route returns **422 without `site_id`**.
- **Re-derive current live values immediately before recording** (§4), and name the window for every
  window-sensitive figure.
- **Note expected behaviours** so you do not mistake them for failures: the executive report returns
  **`text/html` with no `Content-Disposition`** — the dashboard's `studio.js executive()` fetches the body and
  **downloads** `surveillance-report-<session>.html` (it does **not** open a tab; open it from the downloads bar);
  the health CSV is
  **district-wide** (the proxy drops `site_id`); the transcript returns `Content-Disposition: attachment`.
- **The Studio requires the Analyst persona.** Select it in the dashboard persona control before recording; the
  composer is disabled for every other persona. Personas are a demo policy control, not authentication.
- **`rank_wards`'s `fhir_urls` hard-codes a `|oah-demo` suffix** regardless of `OAH_DATASET_TAG`. Never present
  that string as the live evidence tag — use the overview/transcript scope line for the tag.

## 7. Writes, scope and preservation

- Write production assets **only** under `video/` (and the repository's established production subfolders under
  `vidkit/` / `video/produce/` if you use that tooling).
- Do **not** modify application code, configuration (`.env`), fixtures, source data (`demo/`), or existing
  user-owned media.
- Preserve user-owned existing media; replace only the outputs explicitly named in this prompt.
- Do **not** upload, reseed, ingest, or mutate the shared FHIR dataset to obtain a shot. If a scene needs a live
  write, require an isolated FHIR server, `FHIR_UPLOAD_ENABLED=false` (build-not-send), or an explicitly
  approved, uniquely scoped dataset tag.

## 8. Deliverables — produce all of these

1. **Final narration source** — `video/narration.md`: one spoken block per scene with timings, stage directions
   in `[brackets]`, matching the plan's §9.7 script (conversational; carries the synthetic-data and
   association-not-causation disclosures; states a window for every window-sensitive figure).
2. **Timed subtitle file** — `video/narration.srt`: the same narration as SRT cues, ≤ 2 lines and ≤ 42
   characters per line, synchronized to the final edit.
3. **Final shot/recording checklist** — `video/shot-list.md`: per scene, the exact URL, click path, typed
   prompt/command, expected response, and start/stop marks (supersede the older shot-list).
4. **Card and bridge assets** — under `video/scene-cards/` and `video/diagrams/`: title, boundary/recipient
   overlays, the concise provenance bridge, and the end card (with `oah-demo-final`, "shared HAPI FHIR
   sandbox", "synthetic demonstration data", "prototype screening references", "association, not causation").
5. **Recorded/captured scene media** — under `video/_capture/` (or the established capture folder); or explicit,
   clearly-labelled placeholders when a capture is genuinely impossible.
6. **Assembly project/script** — using the repository's established tooling (`video/assemble.sh` and/or the
   `vidkit` spec/provider), parameterised so only input clip paths need editing, with a duration guard so the
   output cannot exceed 5:00.
7. **Final video file** — `video/oneaquahealth-demo.mp4` (or the established output path): 1920×1080, H.264,
   with burned-in or sidecar captions and narration audio.
8. **Thumbnail** — `video/thumbnail.svg` (1280×720): title + "Yamuna at ITO Bridge" + synthetic-data tag.
9. **Verification report** — `video/verification.md` containing: exact final duration; resolution; audio/caption
   status; per-scene provenance (recorded live / deterministic fallback / generated graphic); each scene's
   classification; every on-screen figure with the route and timestamp it was re-derived from; and any
   deviation from the plan.

If your session has a TTS capability, you may additionally generate `video/narration.<ext>`. Do not synthesize
the product UI or charts.

## 9. Hard stop conditions

Stop production and report to me (do not ship a misleading cut) if any of these is true:

- The running gateway's dataset tag is not the story tag, or the story station is missing environmental and
  health data for the window (a 404 from `/api/live/sites/yam-ito`).
- Model access is unavailable for the real Studio scene (Scenes 4–6), and I have not approved a labelled
  alternate cut.
- A Studio run completes without a session id.
- The transcript or executive report is no longer accessible when needed.
- The grounding verdict is ungrounded, or any figure that would appear in narration is unsupported by the
  retrieved data.
- An artifact's response does not match its expected MIME type or schema (CSV/Bundle/report).
- A scene presented as live would show mock content or the mock deck.
- The assembled runtime exceeds **5:00.**

## 10. Proportional fallbacks

- **Nondeterministic Studio run:** retry or recapture using the **same truthful question**. Never fabricate a
  result and never edit terminal output to look like the agent.
- **Deterministic routes** (`/api/officer/{wards,trend,profile,persistence,offset,report/facts}`) may be used
  only for verification, for appendix material, or for an **explicitly labelled** alternate shot — never as the
  main cut's agent.
- **Stale data:** refresh (F5 / `?refresh=true`) and re-record rather than reusing an old capture.
- **A capability that will not record reliably:** omit it (or move it to the appendix) rather than inventing a
  successful result.

## 11. Acceptance criteria — self-check before returning

- [ ] Runtime between **3:00 and 5:00** (state the exact final duration).
- [ ] A **real live Studio run** is shown (streamed tool calls, not terminal output standing in for the agent).
- [ ] At least one tool's **arguments and FHIR evidence URL** are visible.
- [ ] At least **two model-selected visual forms** are shown.
- [ ] The **grounding verdict and its limitation** are visible.
- [ ] The **transcript** is opened; the **executive report** is opened with this run's actual figures and an
      embedded chart.
- [ ] The **readings CSV and health CSV** are visibly distinguished.
- [ ] The **FHIR Bundle** shows `resourceType`, `type: collection`, and the dataset tag.
- [ ] No mock-only capability is presented as live; the mode indicator reads **Live adapter** throughout.
- [ ] The narration states **synthetic demonstration data** and the **association-not-causation** boundary at
      least once each, and they are visible on screen.
- [ ] No stale number: every window-sensitive value names its window and was re-derived before recording.
- [ ] Thresholds are always "prototype screening references", never "legal limits".
- [ ] No generated product UI — every product frame is a real recording.
- [ ] No application code, config, fixture, or data file was modified; only production assets under `video/`
      (and approved production subfolders) changed.

## 12. What to return to me

1. The final runtime and a one-line summary of what was produced.
2. The list of files written or replaced, with their paths.
3. Any discrepancy found between the plan, the code, and the running services — stated plainly.
4. Which scenes were recorded live, which used a labelled deterministic fallback, and which were generated
   graphics.
5. Any scene you could not record reliably, and what you did instead.
6. Confirmation that only production assets under `video/` were modified.

Begin by reading `oneaquahealth-demo-video-plan.md`, then run the §2 preflight and report its result before
generating any asset.
