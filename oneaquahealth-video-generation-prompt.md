# Video generation prompt — OneAquaHealth, "One river, two kinds of evidence"

> **How to use this file.** Open a new chat session whose working directory is this repository
> (`/home/anindyasundar-bera/Projects/OneAquaHealth`). Copy **everything from the line that begins
> `You are a video-production agent…` down to the very end of this file**, and paste it as your first message.
> Everything below the `---` divider on the next lines is the prompt; the divider itself is not.
> The prompt is self-contained — it tells the new session to read `oneaquahealth-demo-video-plan.md` and the
> repository, then produce the video production kit.

---

You are a video-production agent working inside the **OneAquaHealth** repository. Your job is to turn an
existing, approved plan into a finished **3–5 minute** demo video (and the assets needed to assemble it).

Do not re-invent the story. The authoritative plan is:

`oneaquahealth-demo-video-plan.md`

Read it first, in full, and treat it as the source of truth. Then read the code and fixtures it cites so that
every on-screen value you emit is real and current. Where the plan and the live code disagree, **report the
discrepancy to me and build around what the code actually does** — never paper over it.

## 0. Non-negotiable constraints

1. **Live-data test (governing rule).** A capability may appear in the video **only if it still makes sense
   when every record comes from the live FHIR server.** Do not use, screenshot, or narrate anything that
   exists only in the dashboard's mock fixtures: no `?mode=mock`, no relationship graph, no mock report
   lifecycle, no mock run history/retry, no simulated persona authorization. (The plan still *classifies*
   those as `MOCK` / `NOT IMPLEMENTED` — that classification is documentation, not a demo asset.)
2. **No mock content on screen.** The evidence dashboard stays at `http://127.0.0.1:8090/?mode=live`
   throughout. If any frame shows the mock deck, the video is wrong.
3. **Runtime: 3–5 minutes, hard ceiling.** Target ≈ 4 min 30 s. Never exceed 5:00.
4. **Synthetic-data disclosure is mandatory.** The dataset is synthetic demonstration data. State this on
   screen and in narration. Never present it as observed CPCB / IDSP / IHIP / state-board data.
5. **Scientific boundary is mandatory.** Co-location, a temporal offset, and parallel trends justify
   *investigation*; they do **not** prove that river conditions caused the health pattern. Never say or imply
   "caused", "proves a causal lag", "identifies a specific discharge", "legal limit", or "a real event". Safe
   phrases: "a signal worth investigating", "co-located records", "a descriptive pattern", "screened against
   the prototype reference", "the largest change appears between these monitored stations", "the available
   evidence does not establish attribution or causation".
6. **Do not modify application code, configuration, fixtures, or data.** You may only add production files
   (scripts, captions, SVGs, audio, assembly scripts, a production folder). If a scene cannot be recorded
   reliably, say so and use the plan's deterministic live fallback instead.
7. **Never invent commands, routes, values, resources, or runtime behavior.** If something is not verified in
   the repo or the running services, do not put it on screen.

## 1. Preflight (do this before generating anything)

Confirm the environment the video depends on. All read-only.

```bash
# services up?
curl -s -m 5 http://127.0.0.1:8000/health          # {"status":"ok"}
curl -s -m 5 http://127.0.0.1:8090/health          # {"status":"ok", ...}

# dataset tag MUST be oah-demo-final (the seeded Indian series). If not, stop and tell me.
curl -s -m 20 http://127.0.0.1:8000/api/info | grep -o '"dataset_tag": *"[^"]*"'

# the story station must resolve (28 points). If it returns 0, the tag drifted — tell me, do not re-seed.
curl -s -m 60 "http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28"

# dashboard live station must be 200
curl -s -m 60 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/api/live/sites/yam-ito

# optional: model access for the Studio narration scene
[ -n "${OPENAI_API_KEY:-}" ] && echo "key: set" || echo "key: NOT set -> use the deterministic fallback"
```

If the dataset tag is not `oah-demo-final`, or `yam-ito` returns 0 points, **stop and report** before generating.
If `OPENAI_API_KEY` is not set, generate the video using the **deterministic live routes** for the Studio
scenes (see §4, "Studio fallback") exactly as the plan specifies — do not film a stuck "Investigating" panel.

## 2. The story (do not change it)

**One river, two kinds of evidence.** The Yamuna at ITO Bridge (`yam-ito`): environmental screening evidence
and notified population-health surveillance, both viewed through the **same FHIR `Location`**. The video is a
single bounded investigation, not a feature tour.

Narrative beats, in order:

`What is happening?` → `What evidence do we have?` → `What supports the assessment?` → `Is it isolated or
sustained?` → `Where does the change appear?` → `Where did the records come from?` → `How did different inputs
become FHIR data?` → `How does that evidence return to the user?`

## 3. Scene plan (re-verify against the plan, then lock timing)

| # | Time | Scene | Screen / action | Must be live |
|---|---|---|---|---|
| 0 | 0:00–0:10 | Title card | "One river, two kinds of evidence" / "Yamuna at ITO Bridge — synthetic demonstration dataset" / strip: Environmental measurements · Notified population health · HL7 FHIR R4 | n/a (card) |
| 1 | 0:10–0:32 | Scope & mode | `http://127.0.0.1:8090/?mode=live`; station = **Yamuna at ITO Bridge**; point at the `Live adapter` indicator and the scope line `Dataset tag oah-demo-final on https://hapi.fhir.org/baseR4` | yes |
| 2 | 0:32–1:02 | Two kinds of evidence | Station **Context** tab: environmental readings (faecal coliform, BOD, DO) + health measures (acute diarrhoeal disease) at one Location. | yes |
| 3 | 1:02–1:28 | What deserves attention | **Evidence** tab; open one finding's drawer → `FHIR_OBSERVATION` (the reading) + `THRESHOLD_RULE` (the CPCB basis). | yes |
| 4 | 1:28–1:38 | Boundary card | Lower-third: "Co-location is not causation." | n/a (card) |
| 5 | 1:38–2:08 | Open Studio | Assistant panel button **Open Surveillance Studio**; scope = **Current station**; prompt: `Investigate the Yamuna at ITO Bridge over the last month.`; **Run** | yes (needs `OPENAI_API_KEY`) |
| 6 | 2:08–2:45 | Watch the work | Streaming tools (get_thresholds, rank_wards, show_trend, show_river_profile, show_persistence), the two-panel trend, the Yamuna profile (**Wazirabad → ITO → Okhla**), the persistence strip, the grounding chip | yes |
| 7 | 2:45–3:08 | Honest label | Descriptive peak offset: "notified-case peak 9 days after the water peak", with its caveat read aloud | yes |
| 8 | 3:08–3:55 | Provenance | Terminal: run the `iot` sample through the real pipeline; show `[HIGH] yam-ito (delhi)` alert and the mapped resource counts | yes |
| 9 | 3:55–4:30 | Convergence + close | Three channel inputs (MQTT / RabbitMQ / HTTP+CSV) → one tagged transaction Bundle; back to live `yam-ito`; end slate with the value sentence | yes |

The exact per-scene detail — what is visible, presenter action, technical event, code source — is in the plan
(§4). Follow it. Every scene marked "yes" must be a **real screen recording of the running product**, not a
generated animation.

## 4. Verified values you may show (all from `oah-demo-final`, read-only)

Confirm each of these live before you burn it into a caption or the narration. If any differs, use the live
value and flag the change to me.

| Quantity | Value |
|---|---|
| ITO faecal coliform, latest | **25 070 MPN/100 mL** vs criterion **2 500** → **10.03×** |
| ITO coliform, 14-day change | recent mean **37 775.21** vs prior **20 433.36** → **+84.9 %** |
| Ward priority | `['yam-ito']`; ADD change **+140.4 %** (Okhla −6.4 %, Dharavi −10.3 %) |
| Yamuna profile | Wazirabad **886** (within) → ITO **29 104** (11.64×) → Okhla **33 127** (13.25×); largest step **32.84× over 12 km** |
| Persistence | yam-ito **28/28** days over; longest run 28 |
| Descriptive peak offset | water peak 2026-09-24, health peak 2026-10-03 → **+9 days**; **4** weekly health points |
| Ingested sample (`iot`) alert | HIGH: coliform **84 802** (33.92×), BOD 16.8, DO 0.9, NH₃-N 5.6 → `Device×1, Observation×5, Location×5, Specimen×5` |

**Studio fallback (no `OPENAI_API_KEY`):** do not film the streamed model panel. Instead record the
deterministic live routes and narrate them — these satisfy the live-data test with no model:

```bash
curl -s "http://127.0.0.1:8000/api/officer/wards?days=28"
curl -s "http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28"
curl -s "http://127.0.0.1:8000/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28"
curl -s "http://127.0.0.1:8000/api/officer/persistence?days=28"
curl -s "http://127.0.0.1:8000/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28"
curl -s "http://127.0.0.1:8000/api/officer/report/facts?days=28"
```

## 5. Deliverables — produce all of these

Create a folder `video/` in the repo root and write:

1. **`video/narration.md`** — the final voiceover script, one spoken line per scene, with timings, exactly as
   the plan's §5 script (already conversational, ~450–600 words total). Include `[stage directions]` in
   brackets as non-spoken notes. This is the TTS/voice-talent source.
2. **`video/narration.srt`** — the same narration as an SRT caption file, one cue per sentence or two, timed to
   the scene table. Must be readable at 2 lines / ≤ 42 chars per line.
3. **`video/scene-cards/*.svg`** — restrained title/end/boundary cards, one file per card:
   - `00-title.svg` (Scene 0)
   - `04-boundary.svg` ("Co-location is not causation.")
   - `09-end.svg` (value sentence + synthetic-data + prototype-screening disclaimer)
   Include the dataset tag `oah-demo-final` and "shared HAPI FHIR sandbox" on the end card. Keep the product UI
   central; cards are minimal.
4. **`video/diagrams/*.svg`** — the two explanatory graphics the plan calls for:
   - `two-streams.svg` (Scene 2/9: environmental lane vs health lane meeting at "Shared FHIR Location: yam-ito")
   - `convergence.svg` (Scene 9: MQTT / RabbitMQ / HTTP+CSV → one shared pipeline → tagged transaction Bundle,
     labelled with `oneaquahealth/sensors/+/+`, `ingestion.citizen_surveys`, `POST /ingest`,
     `POST /ingest/public-health/csv`)
5. **`video/shot-list.md`** — a precise recording runbook: per scene, the exact URL, the exact click path, the
   exact typed prompt/command, the expected response, and the start/stop marks. This is what a human operator
   follows while screen-recording. Pull the commands verbatim from the plan's §6.
6. **`video/assemble.sh`** — a template ffmpeg assembly script that concatenates the title card, the screen
   recordings, the diagram overlays, the narration audio, and burns in `narration.srt`. Parameterise the input
   clip paths at the top so the operator only edits paths. Include a `-shortest`/duration guard so the output
   cannot exceed 5:00.
7. **`video/thumbnail.svg`** — one 1280×720 thumbnail: title + "Yamuna at ITO Bridge" + synthetic-data tag.

If your session has a TTS or text-to-video capability available, you may additionally generate:
- **`video/narration.<ext>`** — spoken audio from `narration.md` (measured pace, calm, ~150 wpm, total ≤ 4:40).
- **B-roll only for the non-UI segments** (title card, boundary card, convergence animation, end card). Do
  **not** synthesize the product UI or the charts — those must be real screen recordings.

## 6. If you use a text-to-video model for B-roll, use this prompt (non-UI segments only)

> "Minimal, restrained editorial motion graphic on a light off-white background, a thin blue accent line.
> Two parallel horizontal lanes — a water-drop icon on the upper lane labelled 'Environmental measurements
> (daily samples)' and a health/cross icon on the lower lane labelled 'Population health (weekly returns)' —
> converging into a single vertical label 'Shared FHIR Location: yam-ito'. Subtle, slow, documentary tone.
> No text other than the labels. No logos. No people. 16:9, 10 seconds, seamless loop."

Do **not** use a generative model for any frame that shows the dashboard, the Studio, the charts, or a
terminal. Those are captured live.

## 7. Acceptance criteria — self-check before returning

Confirm each, and report pass/fail with evidence:

- [ ] Total runtime is between **3:00 and 5:00** (state the exact final duration).
- [ ] No frame shows mock data or `?mode=mock`; the mode indicator reads **live** throughout.
- [ ] Every number on screen matches a live value in §4 (list where each came from).
- [ ] The narration reads the dataset as **synthetic demonstration data** and states the
      **association-not-causation** boundary at least once (Scene 4 and the close).
- [ ] The peak-offset scene reads its own caveat ("descriptive, not a correlation… only 4 weekly points").
- [ ] Threshold language is "prototype screening reference", never "legal limit".
- [ ] No generated/animated product UI — UI segments are real recordings.
- [ ] If `OPENAI_API_KEY` was absent, the Studio scenes use the deterministic live fallback and the video does
      not show a failed/streaming panel.
- [ ] No application code, config, fixture, or data file was modified.

## 8. What to return to me

1. The final runtime and a one-line summary of what was produced.
2. The list of files written under `video/`.
3. Any discrepancy you found between the plan, the code, and the running services (state it plainly).
4. Which scenes were recorded live vs. used the deterministic fallback vs. were generated graphics.
5. Any scene you could **not** record reliably, and what you did instead.

Begin by reading `oneaquahealth-demo-video-plan.md`, then run the §1 preflight and report its result before
generating any asset.
