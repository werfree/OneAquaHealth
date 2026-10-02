# OneAquaHealth

A One Health interoperability platform: water-quality telemetry, citizen field surveys and
disease-surveillance returns normalised into **HL7 FHIR R4** against the
[OneAquaHealth Implementation Guide](https://hl7.eu/fhir/ig/oah), written to a live FHIR server,
and queried by an analyst agent that shows its working.

Built for **IEEE Global Hackathon 2026, Track 7 — Digital Health Standards**.

> **Why FHIR, in India.** ABDM mandates HL7 FHIR R4 for health data exchange, so an evidence bundle
> from this pipeline attaches to a district incident record natively rather than as a spreadsheet
> somebody retypes. That is the whole argument for the IG, and it is stronger here than in the
> European framing the IG was written for.

---

## Quick start

```bash
python -m pip install -r requirements.txt     # installs all four packages editable
cp .env.example .env                          # then add your OPENAI_API_KEY
./run-demo.sh stack                           # RabbitMQ (needs docker/colima running)
./run-demo.sh app                             # the gateway — leave this running
```

Wait for these two lines before doing anything else:

```
Consuming citizen surveys from ingestion.citizen_surveys
Connected; subscribed to oneaquahealth/sensors/+/+
```

Then open either UI:

| | |
|---|---|
| **Ingestion Gateway** | <http://localhost:8000> — send a feed through, watch every pipeline stage |
| **Surveillance Studio** | <http://localhost:8000/api/officer/panel> — ask a question, the analyst investigates |
| API docs | <http://localhost:8000/docs> |
| Gateway status | <http://localhost:8000/api/info> |

Seed the repository with 28 days of data (takes a few minutes — it is ~190 real uploads):

```bash
./run-demo.sh seed
```

---

## The two UIs

### Ingestion Gateway — `/`

Shows the pipeline doing its job. Pick a source (CPCB telemetry, citizen survey, IDSP return) and it
runs the **real** pipeline, returning each stage: the raw payload, the alert screening raised, the
FHIR Observation produced with the profile the data selected, and the transaction result.

A single **Summary / Reasoning / Data** control sets the depth of the whole page — *what it concluded*,
*why it did that*, *the underlying evidence* — so nothing is hidden and nothing is cluttered.

### Surveillance Studio — `/api/officer/panel`

The end-user tool, for a **District Surveillance Officer** in an IDSP/IHIP district unit deciding
whether a rise in notifications has an environmental explanation worth escalating to the State
Pollution Control Board.

There are no tabs and no fixed workflow. You state an intent; the analyst decides what to do —
including **which visualisation answers the question**, because the charts are tools in the same list
as the data queries. It streams its reasoning, each tool call, and each chart as it is chosen.

Press **Shift+D** (or add `?autorun=1`) for a hands-free demo that drives the real studio.

---

## Architecture

```
MQTT  oneaquahealth/sensors/{city}/{site}  ─┐
RabbitMQ  ingestion.citizen_surveys        ─┼─► envelope ─► OAH model ─► FHIR R4 ─► HAPI server
HTTP  POST /ingest                         ─┘   validate    map          upsert
                                                    │
                                                    └─► threshold screening ─► alert
                                                                                  │
                     Surveillance Studio ◄── analyst agent ◄── FHIR queries ◄──────┘
```

| Package | What it is |
|---|---|
| `oah-pydantic-models/` | The 7 OAH logical models, plus `fhir/` — an executable implementation of the IG's 7 `*2FHIR.fsh` ConceptMaps |
| `oah-ingestion/` | The gateway: envelope validation, threshold alerting, FHIR adapter + client, both UIs, the officer API |
| `oah-agent/` | The analyst: typed FHIR tools, visualisation tools, orchestration, grounding check |
| `oah-demo-publishers/` | Sends one sample down each of the three input channels |

### How a reading becomes FHIR

1. **Validate** — discriminated envelope per stream. Strict units, city allow-list, mandatory
   timezones, pH 0–14, non-negative concentrations, no NaN.
2. **Screen** — against CPCB criteria *before* FHIR conversion, so an operator learns about an
   exceedance even if the FHIR server is down.
3. **Map** — a reading carrying min/max/avg becomes a `StructuredIndicator` →
   `observation-with-component-oah`; a bare reading becomes a `SimpleIndicator` →
   `observation-indicators-oah`. **The data picks the profile**, which is the distinction those two
   profiles exist to draw.
4. **Upsert** — a transaction bundle of conditional-free `PUT`s with deterministic ids, so replaying
   an event updates the same resources instead of duplicating them. That is what makes the demo
   re-runnable.

### Profiles produced

| Source | OAH profile |
|---|---|
| Sensor reading with statistics | `observation-with-component-oah` |
| Sensor spot reading, citizen survey answer | `observation-indicators-oah` |
| IDSP syndromic return, cohort risk | `observation-health-measure-oah` |
| Ward cohort | `group-oah` |
| Site | `location-oah` · `specimen-oah` |

---

## The analyst

### It never writes a FHIR query

`docs/plan.md` describes the AI layer as a "natural language to FHIR REST URL" translator. That was
deliberately **not** built. A model writing a URL as free text can invent a search parameter, and
FHIR answers an unknown parameter with an empty bundle and HTTP 200 — a wrong answer indistinguishable
from "no data". The model picks a **typed tool**; the code builds the URL.

### Grounding is verified, not requested

Every numeric literal in an answer is checked against the figures the tools actually returned —
deterministic Python, no second model. It exists because the assistant was once caught reporting
*"above the safe level of 10 mg/L"*, where 10 was a search filter it had chosen itself.

The check is narrow and says so in its own output: it verifies that figures came from the data, **not**
that they are used in a true sentence, and a claim with no number in it is not checked at all.

### Correlation is computed in Python

`briefing.py` derives exceedances and co-location; the model only narrates facts already fixed. An LLM
asked to "find correlations" in a JSON blob produces confident arithmetic nobody checked.

### Tools the analyst can choose from

| Data | Analysis | Visualisation |
|---|---|---|
| `get_thresholds` | `rank_wards` | `show_stats` |
| `list_sites` | `get_trend` | `show_matrix` |
| `search_observations` | `peak_offset` | `show_ranking` |
| `get_site_profile` | | `show_trend` |
| `get_cohort` | | `show_scatter` |
| | | `show_river_profile` |
| | | `show_persistence` |

Three worth knowing about:

- **`show_river_profile`** plots one indicator along a river in flow order and names the step between
  consecutive stations. On the demo data: coliform rises **42.6× over the 12 km** between Wazirabad
  and ITO, then is flat to Okhla. *"The Yamuna is polluted"* is not actionable; *"something discharges
  in these 12 km"* is a referral the SPCB can work.
- **`show_persistence`** distinguishes a one-off exceedance from a sustained condition. A latest-value
  view cannot tell them apart, and they warrant different responses.
- **`peak_offset`** reports days between the water peak and the case peak — a **descriptive offset,
  not a correlation**. The window holds four weekly surveillance points; a coefficient on four points
  would be a statistic in name only.

---

## Reports and exports

| | |
|---|---|
| **Executive report** | `POST /api/officer/studio/executive` — situation, findings table, assessment, figures, actions ranked by urgency, limitations, signature block, appendix of queries. A4 print CSS; *Save as PDF* in the page. |
| **Full transcript** | `GET /api/officer/studio/report/{session}` — every action in order with its queries, for auditing *how* a conclusion was reached |
| Readings CSV | `GET /api/officer/export/readings.csv?days=28` — criterion and exceedance factor on every row |
| IDSP returns CSV | `GET /api/officer/export/surveillance.csv?days=90` — case counts **and** denominators |
| FHIR evidence bundle | `GET /api/officer/export/bundle.json?site_id=…` — attaches to an ABDM-aligned record |
| Derived facts | `GET /api/officer/report/facts?days=28` — what a report asserts, no model involved |

---

## Configuration

All optional; every value below is the default.

| Variable | Default | |
|---|---|---|
| `OPENAI_API_KEY` | — | **required** for the analyst. Put it in `.env` (gitignored) |
| `OPENAI_MODEL` | `gpt-4o` | |
| `FHIR_BASE_URL` | `https://hapi.fhir.org/baseR4` | point at your own server |
| `FHIR_UPLOAD_ENABLED` | `true` | `false` runs everything except the POST |
| `OAH_DATASET_TAG` | `oah-demo` | scopes every query; the public sandbox holds other parties' OAH data |
| `OAH_CITIES` | `delhi,kanpur,…` | city allow-list |
| `OAH_SITES_FILE` | `demo/sites.json` | your own station gazetteer |
| `MQTT_HOST` | `broker.hivemq.com` | **public broker** — use your own for an isolated demo |
| `RABBITMQ_HOST` | `localhost` | |
| `APP_HOST` / `APP_PORT` | `0.0.0.0` / `8000` | |
| `DASHBOARD_PORT` | `8090` | separate evidence dashboard |
| `OAH_LIVE_BASE_URL` | `http://127.0.0.1:8000` | live-gateway mode for that dashboard |
| `DASHBOARD_DEFAULT_THEME` | `aqua` | theme selector can override per browser |

---

## Evidence dashboard

The separate evidence dashboard runs alongside the ingestion gateway. Install and start it from
the repository root:

```bash
python -m pip install -e ".[dev]"
oah-dashboard
```

It opens at <http://localhost:8090> by default and starts in mock mode with sample observations,
findings, and run/report workflows. Set `OAH_LIVE_BASE_URL` and open
<http://localhost:8090/?mode=live> to connect it to the live gateway; live mode uses an allow-listed
same-origin proxy for the existing gateway routes. Durable run history, authorization, evidence
graph, and report storage remain mock-backed — see `dashboard/API-MAPPING.md` for the boundary.

---

## Testing

```bash
export PYTHONPATH=oah-agent/src:oah-ingestion/src:oah-pydantic-models/src
for d in oah-agent oah-ingestion oah-pydantic-models; do python3 -m unittest discover -s $d/tests; done
```

**79 tests**, none of which touch the network. Several are regressions from real failures:

- `test_fhir_paging.py` — a server page cap silently truncated results, and with an ascending sort the
  rows dropped were the **newest**, so "the latest reading" came back 11 days stale.
- `test_studio.py` — grounding counted only what the model was shown, so every figure read off a chart
  was flagged unsupported.
- `test_fhir_mappers.py` — the FHIR subpackage shipped unimportable and nothing caught it.
- `test_analysis.py` — the river profile must attribute a load to the right stretch; a wrong one sends
  a sampling team to the wrong place.

---

## Please read this before presenting any of it

- **The readings are synthetic.** `demo/timeseries/` is generated by `demo/generate_timeseries.py`,
  shaped to be realistic against CPCB's reported picture of these reaches. It is **not** observed
  measurement. No code path is mocked — the data is genuinely ingested, converted, uploaded and queried
  back — but the numbers are demonstration data.
- **Thresholds are screening values, not enforcement limits.** CPCB Primary Water Quality Criteria for
  Bathing Waters and IS 10500:2012. The Designated Best Use class for a specific reach is set by the
  State Pollution Control Board.
- **Co-location is an association, never causation.** The system says this everywhere and so should we.
- **Station coordinates and `flow_km` are approximate**, for ordering and mapping, not surveyed.
- **The public MQTT broker and the public FHIR sandbox are shared.** Anything written there is visible
  to anyone.

---

## Known gaps

- `observation-with-component-oah` has almost no instances — the time-series generator does not emit
  min/max/avg, so that profile is barely exercised.
- Nine `Location` resources exist for six stations; three survive from an earlier European framing.
- IDSP returns are weekly, which caps any temporal analysis at a handful of points. The offset analysis
  is honest but weak, and only becomes meaningful with daily returns — a data-collection change.
- Alerts reach a log and `subscribe()`, but nothing is wired to email, SMS or a duty pager.
- No authentication or audit trail. Any tool informing a health decision needs a record of who asked
  what, when.
- The studio holds sessions in memory, so a restart loses report downloads for runs in flight.

## Open questions for the team

1. **Where is the upstream `oah` IG repo?** Every model and mapper docstring cites
   `oah/input/fsh/model-maps/*.fsh` and `oah-codeSystem.fsh`. Neither is in this repository, so no
   mapping can be verified against its source of truth.
2. `docs/plan.md` still marks all four phases complete. Phases 1, 2 and 4 largely are now; Phase 3 is
   the studio rather than the Streamlit app it describes. **That file is the one place the repo
   overstates itself** and should be rewritten.
3. Is this affiliated with the OneAquaHealth EU project, or independent? Earlier demo payloads named
   StreamKeepers and Enora as if they were live integrations.
4. Is there real pilot data, and are we licensed to publish the health figures?
