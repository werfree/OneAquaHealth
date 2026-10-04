# Example: OneAquaHealth demo video

This reproduces `video/oneaquahealth-demo.mp4` — *"One river, two kinds of evidence"* —
from the running OneAquaHealth services, using vidkit.

## Prerequisites

* The gateway on `:8000` with `OAH_DATASET_TAG=oah-demo-final` and the dashboard on `:8090`
  (see the repo's `run-demo.sh` / `README.md`).
* `ffmpeg`, `rsvg-convert`, `playwright` (+ a Chrome build), `piper-tts` (+ a voice model).
* A piper voice. Fetch one with `python -m piper.download_voices en_US-lessac-medium`
  and point `voice.model` in `video.yaml` at the resulting `.onnx`.

## Run

```bash
# from the repo root
PYTHONPATH=vidkit vidkit doctor vidkit/examples/oneaquahealth/video.yaml
PYTHONPATH=vidkit vidkit plan   vidkit/examples/oneaquahealth/video.yaml

# render into ./video (overwrites the committed demo video)
PYTHONPATH=vidkit vidkit build  vidkit/examples/oneaquahealth/video.yaml --out video

# or into a scratch folder
PYTHONPATH=vidkit vidkit build  vidkit/examples/oneaquahealth/video.yaml --out vidkit/.out
```

## What each file is

| File | Role |
|---|---|
| `video.yaml` | The spec — project, voice, narration source, captures, charts, scenes, guards. |
| `narration.md` | The spoken script. Scenes are headed `## Scene N — … · mm:ss–mm:ss`; spoken lines are `**bold**`; `[brackets]` are stage directions. |
| `provider.py` | The bridge to OneAquaHealth: fetches live values read-only, runs the `iot` sample through the real pipeline (upload disabled), and registers four custom panels. |
| `assets/*.svg` | Title / boundary / end cards and the two explanatory diagrams. |

## Why it is a good reference

* **Real UI, guarded** — five Playwright captures, each asserting `#mode-indicator` contains
  *"Live adapter"*, so the build can never silently film mock mode.
* **Live numbers, never hard-coded** — every chart value comes from the gateway or from the
  repo's own screening code; the spec only says *what* to show.
* **Deterministic fallback** — with no `OPENAI_API_KEY`, Scenes 5–7 use the
  `/api/officer/*` routes instead of the streamed model panel (no stuck "Investigating").
* **Guarded honesty** — `guard.banned` / `guard.required` assert the narration never claims
  causation and always discloses that the data is synthetic.
