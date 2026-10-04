# OneAquaHealth demo video — how it was produced

**Output:** `video/oneaquahealth-demo.mp4` — 1920×1080, 30 fps, H.264 + AAC, **4:18.73**, burned-in captions.
**Story:** one investigation at one shared FHIR `Location` (`yam-ito`) — environmental screening evidence and
notified population-health surveillance. Live-data test enforced throughout; synthetic-data and
association-not-causation boundaries stated on screen and in narration.

## What is real vs. produced

| Segment | Source |
|---|---|
| Dashboard UI (overview, Context, Evidence drawer) | **Real live captures** of `http://127.0.0.1:8090/?mode=live`, station `yam-ito`, mode indicator **Live adapter** |
| Gateway ingestion dashboard (stage view, cross-domain join) | **Real live captures** of `http://127.0.0.1:8000/` |
| Trend / profile / persistence / offset / ingest panels | **Drawn from live JSON** fetched read-only from the gateway (no live data synthesised, no model) |
| Title / boundary / end cards, two-streams + convergence diagrams | Generated SVG (graphics only — no fabricated UI) |
| Narration audio | Piper TTS (`en_US-lessac-medium`), `--length-scale 1.08` |

No frame shows mock data or `?mode=mock`. No generated/animated product UI.

## Pipeline

```
capture_data.py ──► _build/data/*.json        (read-only live values; ingest runs with FHIR_UPLOAD_ENABLED=false)
panels.py       ──► _build/panels/*.svg       (charts/briefs drawn from that JSON)
(playwright)    ──► _capture/*.png            (real live UI screenshots, 1920×1080@2x)
tts.py          ──► _build/wavs/scene-NN.wav  (per-scene narration)
assemble_video.py ─► oneaquahealth-demo.mp4   (+ retimed narration.srt)
```

`assemble_video.py` sizes each scene's video to that scene's **actual narration duration**, so audio and
video stay in sync, then muxes with `-shortest` and a 300 s ceiling guard.

### Re-run from scratch

```bash
# services must be up (gateway :8000 with OAH_DATASET_TAG=oah-demo-final, dashboard :8090)
.venv/bin/python video/produce/capture_data.py     # read-only live values (no FHIR writes)
#   re-capture live UI (needs playwright + the bundled Chrome):
#   see video/shot-list.md; the captures live in video/_capture/
.venv/bin/python video/produce/panels.py
.venv/bin/python video/produce/tts.py 1.08         # writes per-scene wavs
.venv/bin/python video/produce/assemble_video.py   # builds the mp4 + retimed srt
```

### Dependencies actually used

`ffmpeg` (with `libx264`, `aac`, `subtitles`), `rsvg-convert`, `playwright` (Python) driving
`~/.cache/ms-playwright/chromium-1234`, `piper-tts` + the `en_US-lessac-medium` voice. `ffprobe` is **not**
required (durations are read from `ffmpeg`).

## Verified live values on screen (all from `oah-demo-final`)

| Quantity | Value |
|---|---|
| ITO faecal coliform, latest | 25 070 MPN/100 mL vs 2 500 → 10.03× |
| 14-day change | recent 37 775.21 vs prior 20 433.36 → +84.9 % |
| Ward priority | `['yam-ito']`, ADD +140.4 % (Okhla −6.4 %, Dharavi −10.3 %) |
| Yamuna profile | Wazirabad 886.14 → ITO 29 104.29 (11.64×) → Okhla 33 126.75 (13.25×) |
| Largest step | 32.84× over 12 km |
| Persistence | 28/28 days over; longest run 28 |
| Descriptive peak offset | water 2026-09-24, health 2026-10-03 → +9 days; 4 weekly points |
| Ingested `iot` sample | HIGH: coliform 84 802 (33.92×), BOD 16.8, DO 0.9, NH₃-N 5.6 → Device×1, Observation×5, Location×5, Specimen×5 |

## Governance

- Dataset is **synthetic demonstration data**; thresholds are **prototype screening references** — never
  "legal limit".
- The narration states the **association-not-causation** boundary (Scene 4 and the close) and reads the
  peak-offset caveat verbatim ("descriptive… not a correlation… only 4 weekly points").
- `OPENAI_API_KEY` was absent, so Scenes 5–7 use the **deterministic live fallback** (`/api/officer/*`) — no
  stuck "Investigating" panel is shown.
- **No application code, configuration, fixture, or data file was modified.** Read-only queries only; the
  ingest demonstration ran with `FHIR_UPLOAD_ENABLED=false` (result `BUILT_NOT_SENT`).
