# Shot list / recording runbook — "One river, two kinds of evidence"

**Authoritative plan:** `oneaquahealth-demo-video-plan.md` (§4 storyboard, §6 runbook, §7 risks).
**Target runtime:** 3:00–5:00, target ≈ 4:30. **Hard ceiling:** 5:00.
**Governing rule:** every "LIVE" scene is a real screen recording of the running product. Never open `?mode=mock`. The mode indicator must read **Live adapter** in every frame.

> **Environment on this machine (verified 2026-10-04, read-only).** `OPENAI_API_KEY` is **not set**, so the
> Studio's streamed, model-narrated investigation cannot run. **Scenes 5–7 use the deterministic live
> fallback** (terminal routes + rendered charts), exactly as the prompt permits. Do not film a stuck
> "Investigating" panel. If you later set a key, you may record the streamed version instead.

---

## Pre-flight (before every take)

```bash
# services
curl -s -m 5 http://127.0.0.1:8000/health            # {"status":"ok"}
curl -s -m 5 http://127.0.0.1:8090/health            # {"status":"ok", ...}

# tag MUST be oah-demo-final
curl -s -m 20 http://127.0.0.1:8000/api/info | grep -o '"dataset_tag": *"[^"]*"'

# story station MUST resolve to 28 points
curl -s -m 60 "http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28" \
  | .venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print('points',d['points'],'latest',d['latest'])"
# expect: points 28 latest 25070.0

# dashboard live station MUST be 200
curl -s -m 60 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/api/live/sites/yam-ito

# model access
[ -n "${OPENAI_API_KEY:-}" ] && echo "key: set" || echo "key: NOT set -> deterministic fallback (this machine)"
```

**Stop and report** if the tag is not `oah-demo-final` or `yam-ito` returns 0 points. Do **not** re-seed.

### Terminal layout

| Terminal | Purpose | Command |
|---|---|---|
| **A** | Gateway (logs) | `python3 -m oah_ingestion.app` |
| **B** | Shell (curl / sample) | — |
| **C** | Dashboard | `oah-dashboard` |

Browser window: `http://127.0.0.1:8090/?mode=live` (bookmark it; never touch the "About this demo" mode link).

**Recording settings (OBS / equivalent):** 1920×1080, 30 fps, browser at 100% zoom, hide bookmarks bar and any personal tabs, blur any API keys. Terminal font ≥ 16 px so the alert block is legible.

**Start/stop marks** — for each scene, begin the clip ~1 s before the first action ("start mark") and hold ~1 s after the last action ("stop mark") so the editor has handles.

---

## Scene 0 — Title card · 0:00–0:10

| | |
|---|---|
| **Type** | Generated graphic (not a recording) |
| **Asset** | `video/scene-cards/00-title.svg` → render to 10 s clip |
| **Start / stop** | Card holds the full 10 s |
| **Narration** | Scene 0 of `video/narration.md` |

No live action. If compositing manually, this is a still + slow 4 % push-in.

---

## Scene 1 — Scope & mode · 0:10–0:32

| | |
|---|---|
| **URL** | `http://127.0.0.1:8090/?mode=live` |
| **Click path** | (1) Load the URL. (2) Confirm top-bar mode indicator reads **Live adapter**. (3) Set the station selector to **Yamuna at ITO Bridge**. (4) Hover/point at the scope line under the metric tiles. |
| **Typed** | none |
| **Expected on screen** | Mode indicator **Live adapter**; station **Yamuna at ITO Bridge**; sidebar **Overview / Ingestion / Reports / Surveillance**; metric tiles (sites in scope, loaded observations, screening findings, co-located sites); scope line `Dataset tag oah-demo-final on https://hapi.fhir.org/baseR4`. |
| **Backing route** | `GET /api/live/overview` → gateway `GET /api/overview` → `dataset_briefing(tag)` |
| **Start / stop** | Start on page load; stop after dwelling on the scope line |

> **Do not** let the shot linger on the "co-located sites" tile in a way that implies ITO is in it — the
> dashboard tile does not fire for ITO (no risk scores). See Scene 6 note.

---

## Scene 2 — Two kinds of evidence at one Location · 0:32–1:02

| | |
|---|---|
| **URL** | `http://127.0.0.1:8090/?mode=live` (station stays `yam-ito`) |
| **Click path** | Station workspace → **Context** tab (default). Scroll the observations table. Highlight one **faecal coliform** row and one **acute diarrhoeal disease** row. |
| **Typed** | none |
| **Expected on screen** | Observations table mixing environmental readings (faecal coliform, BOD, dissolved oxygen) with health measures (acute diarrhoeal disease), each with effective dates; both rows cite the same Location `yam-ito`. |
| **Backing route** | `GET /api/live/sites/yam-ito` → gateway `GET /api/sites/yam-ito` → `site_briefing(include_observations=True)` |
| **Overlay** | Optional inset: `video/diagrams/two-streams.svg` |
| **Start / stop** | Start as the tab renders; stop after highlighting the second row |

**Do not click the Relationships tab** (mock-only in live mode; excluded from this cut).

---

## Scene 3 — What deserves attention · 1:02–1:28

| | |
|---|---|
| **URL** | `http://127.0.0.1:8090/?mode=live` |
| **Click path** | Click **Evidence** tab → click a threshold finding to open its **drawer** → point at the two derived records. |
| **Typed** | none |
| **Expected on screen** | Finding text, e.g. *"Faecal coliform above prototype screening value — 25 070 MPN/100 mL against 2 500 (≈10×)"* with basis *"CPCB Primary Water Quality Criteria for Bathing Waters — maximum permissible 2500 MPN/100mL (desirable 500)"*. Drawer shows **Record type `FHIR_OBSERVATION`** (the reading) and **`THRESHOLD_RULE`** (the screening basis), plus an id of the form `live-evidence-exceedance-…-yam-ito`. |
| **Backing code** | `api.js liveFindings()/liveEvidence()`; `thresholds.INDIAN_THRESHOLDS`; `briefing._exceedances()` |
| **Start / stop** | Start before clicking Evidence; stop with the drawer open |

> The `live-evidence-…` id is a **dashboard-level reference**; the underlying record is a real FHIR
> Observation on the server. Say so aloud (narration already does).

---

## Scene 4 — Boundary card · 1:28–1:38

| | |
|---|---|
| **Type** | Generated graphic (lower-third overlay) |
| **Asset** | `video/scene-cards/04-boundary.svg` — composite as a lower-third over a frozen Scene-3 frame |
| **Start / stop** | 10 s hold |
| **Narration** | Scene 4 of `video/narration.md` ("Co-location is not causation. Hold that.") |

---

## Scene 5 — Open the Studio · 1:38–2:08

> **This machine has no `OPENAI_API_KEY` → use the deterministic live fallback.** Film the fallback, not a
> streamed model panel.

### 5A — Optional live UI (only if a key is set)

| | |
|---|---|
| **Click path** | In the assistant panel click **Open Surveillance Studio** (this button renders only in live mode) → scope selector **Investigate: Current station** → type the prompt → press **Run**. |
| **Typed prompt** | `Investigate the Yamuna at ITO Bridge over the last month.` |
| **Backing** | `POST /api/live/studio/run` → gateway `POST /api/officer/studio/run` → `oah_agent.studio.run()` (SSE) |

### 5B — Deterministic fallback (REQUIRED on this machine)

| | |
|---|---|
| **Where** | Terminal B |
| **Commands (run in this order, capture the JSON)** | see block below |
| **Expected** | Real JSON computed in Python from live FHIR — no model involved. |
| **On-screen framing** | Narrate as "the same analyses the Studio calls, computed deterministically from live FHIR." |

```bash
curl -s "http://127.0.0.1:8000/api/officer/wards?days=28"
curl -s "http://127.0.0.1:8000/api/officer/trend?site_id=yam-ito&indicator=faecal_coliform&days=28"
curl -s "http://127.0.0.1:8000/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28"
curl -s "http://127.0.0.1:8000/api/officer/persistence?days=28"
curl -s "http://127.0.0.1:8000/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28"
curl -s "http://127.0.0.1:8000/api/officer/report/facts?days=28"
```

For a legible shot, pretty-print and trim:

```bash
curl -s "http://127.0.0.1:8000/api/officer/profile?river=Yamuna&indicator=faecal_coliform&days=28" \
  | .venv/bin/python -m json.tool | head -40
```

| **Start / stop** | Start before typing the first curl; stop after the last response renders |

---

## Scene 6 — Watch the work · 2:08–2:45

| | |
|---|---|
| **Type** | Charts rendered from the Scene-5 fallback JSON (or the live Studio charts if a key is set) |
| **On screen** | Two-panel trend (coliform above, notified ADD below); Yamuna river profile **Wazirabad → ITO → Okhla**; persistence strip; grounding note. Point at the **Wazirabad → ITO** step. |
| **Verified numbers you may quote** | see table below |
| **Start / stop** | Start on the trend chart; stop on the profile's steep step |

### Verified values (all confirmed live, 2026-10-04)

| Quantity | Value | Endpoint |
|---|---|---|
| ITO faecal coliform, latest | **25 070 MPN/100 mL** vs criterion **2 500** → **10.03×** | `/api/officer/trend` latest / factor |
| ITO coliform, 14-day change | recent mean **37 775.21** vs prior **20 433.36** → **+84.9 %** | `/api/officer/trend` `.change` |
| Ward priority | `['yam-ito']`; ADD change **+140.4 %** | `/api/officer/wards` |
| Comparators | Okhla −6.4 %, Dharavi −10.3 % | `/api/officer/wards` |
| Yamuna profile | Wazirabad **886.14** (within) → ITO **29 104.29** (**11.64×**) → Okhla **33 126.75** (**13.25×**) | `/api/officer/profile` |
| Largest step | **32.84× over 12 km** (Wazirabad → ITO) | `/api/officer/profile` `largest_increase` |
| Persistence | yam-ito **28/28** days over; longest run **28** | `/api/officer/persistence` |
| Descriptive peak offset | water peak **2026-09-24**, health peak **2026-10-03** → **+9 days**; **4** weekly health points | `/api/officer/offset` |

> **Do not** say the dashboard's co-location tile corroborates the Studio finding. The dashboard tile requires
> an exceedance **and** an `elevated_risk` (the Indian series has no risk scores → the tile never fires for
> ITO). The Studio's `co_located` uses a **different** test — a screening flag plus a >15 % rise in notified
> ADD — which is why `yam-ito` appears there with `add_change_pct 140.4`.

---

## Scene 7 — The honest label · 2:45–3:08

| | |
|---|---|
| **Where** | Terminal B (or the live Studio offset card if a key is set) |
| **Command** | `curl -s "http://127.0.0.1:8000/api/officer/offset?site_id=yam-ito&indicator=faecal_coliform&days=28" \| .venv/bin/python -m json.tool` |
| **Expected (verified)** | `"offset_days": 9`, `"health_points": 4`, `"interpretation": "The notified-case peak falls 9 days after the water peak."`, `"caveat": "Descriptive offset between two maxima, not a correlation. This window holds only 4 weekly surveillance points, which cannot support a statistical association. Treat as a prompt to sample, never as evidence of a causal lag."` |
| **On-screen framing** | Highlight `offset_days`, `health_points`, and the `caveat`. Read the caveat aloud, word for word. Never say the word "correlation" except as quoted by the caveat. |
| **Start / stop** | Start before the curl; stop after dwelling on the caveat |

---

## Scene 8 — Where did these records come from? · 3:08–3:55

| | |
|---|---|
| **Where** | Terminal A (gateway logs) + Terminal B (the sample) |
| **Command (no-write, preferred)** | See block below — runs the real pipeline with `FHIR_UPLOAD_ENABLED=false` → `BUILT_NOT_SENT`, nothing is written to the shared sandbox. |
| **Alternative (writes)** | `curl -s -X POST http://127.0.0.1:8000/api/ingest-demo/iot` — only if you accept a write (idempotent upsert) OR have switched `OAH_DATASET_TAG` to a unique value. |
| **Expected alert (verified)** | `[HIGH] yam-ito (delhi) - 2026-09-30T09:00:00+00:00` with `faecal_coliform: 84802.0 MPN/100mL (33.92x threshold 2500.0)`, `bod: 16.8 mg/L (5.6x threshold 3.0)`, `dissolved_oxygen: 0.9 mg/L (5.56x threshold 5.0)`, `ammoniacal_nitrogen: 5.6 mg/L (4.67x threshold 1.2)`. |
| **Expected mapping (verified)** | `{'Device': 1, 'Observation': 5, 'Location': 5, 'Specimen': 5}` |
| **Start / stop** | Start before the command; stop after the resource counts print |

```bash
PYTHONPATH=oah-ingestion/src:oah-pydantic-models/src:oah-agent/src FHIR_UPLOAD_ENABLED=false \
.venv/bin/python -c "
import json, os
os.environ['FHIR_UPLOAD_ENABLED']='false'
from pydantic import TypeAdapter
from oah_ingestion.envelope import IngestionEnvelope, envelope_as_message
from oah_ingestion.pipeline import process
from oah_ingestion.alerts import assess, format_alert
from oah_ingestion.fhir_adapter import envelope_to_fhir
raw=json.load(open('demo/sample_iot_telemetry.json'))
env=TypeAdapter(IngestionEnvelope).validate_python(raw)
print(format_alert(assess(env)))
from collections import Counter
print('RESOURCE COUNTS:', dict(Counter(r.resourceType for r in envelope_to_fhir(env))))
out=process(env, envelope_as_message(env))
print('PIPELINE fhir:', out.get('fhir'))
"
```

> If you instead use the gateway route `/api/ingest-demo/iot`, its response `upload.resources` counts the
> **built transaction entries** (`Location: 1`, deduped), whereas a full client-side map enumerates
> `Location: 5`. Both are honest; narrate which one is on screen. The sample content is identical to the
> values above.

---

## Scene 9 — Convergence + close · 3:55–4:30

| | |
|---|---|
| **Overlay** | `video/diagrams/convergence.svg` (MQTT / RabbitMQ / HTTP+CSV → one pipeline → tagged transaction Bundle) |
| **Then return to** | `http://127.0.0.1:8090/?mode=live`, station `yam-ito`, **Context** tab |
| **Action** | Press **F5** (hard refresh) deliberately, then re-open **Context**. |
| **Expected** | Same station, same two kinds of evidence, mode still **Live adapter**. |
| **End card** | `video/scene-cards/09-end.svg` |
| **Start / stop** | Start on the convergence graphic; stop on the end card hold |

> Refresh clears both the gateway overview cache (60 s, or `?refresh=true`) and `api.js`'s per-station
> `liveStationCache`. Narrate *why* you refresh ("the gateway drops its cache after a successful upload, but
> the browser still needs a refresh").

---

## Banned on camera (recap)

- Any `?mode=mock` frame; the mode indicator must read **Live adapter** throughout.
- The **Relationships** tab; the mock **Reports** lifecycle; run history / retry; persona authorization flows.
- "caused", "proves a lagged effect", "identifies the discharge", "legal limit", "a real event".
- Any generated/animated product UI — UI scenes are real recordings only.

## If a scene fails

Refresh (F5); confirm the backend with the matching `curl`; if it still fails, use the equivalent `curl`
fallback in this runbook. **Never** switch to `?mode=mock` to recover.
