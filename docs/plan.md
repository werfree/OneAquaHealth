
# OneAquaHealth IEEE Global Hackathon 2026: Track 7 Execution Plan

## Executive Summary & Hackathon Vision
Urban aquatic ecosystems face increasing stress from urbanization and climate change, leading to "Urban Stream Syndrome." A critical bottleneck in protecting these blue/green spaces is data fragmentation—environmental sensor feeds, citizen science observations, and public health statistics exist in isolated silos.

This project delivers an end-to-end **One Digital Health Interoperability Platform** for **Track 7: Digital Health Standards**. By leveraging the **HL7 FHIR OneAquaHealth Implementation Guide (OAH IG)**, **FAIR data principles** (Findable, Accessible, Interoperable, Reusable), and the **One Health framework**, our solution connects stream ecosystem health with human community well-being.

---

## System Architecture Overview
Our platform unifies three core capabilities into a single integrated workflow (as illustrated in `system-architecture-diagram.png`):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. DATA INGESTION & OAH FHIR ADAPTER PIPELINE                              │
│ Ingests IoT sensor telemetry & citizen science entries (StreamKeepers/Enora) │
│ Maps inputs to HL7 FHIR OAH IG Profiles:                                    │
│  • location-oah (GIS Stream Sites & SNOMED CT)                              │
│  • observation-indicators-oah (Qualitative Surveys: Vegetation & Flow)       │
│  • observation-with-component-oah (Lab Metrics: pH, Nitrate, Heavy Metals)  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP POST (application/fhir+json)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. CENTRAL INTEROPERABILITY CORE (HAPI FHIR SANDBOX SERVER)                 │
│ Standardized RESTful Repository (/Observation, /Location, /Group)           │
└───────────────────┬─────────────────────────────────────┬───────────────────┘
                    │ HTTP GET (Bundles)                  │ FHIR REST API
                    ▼                                     ▼
┌───────────────────────────────────────┐ ┌───────────────────────────────────┐
│ 3. ONE HEALTH RISK DASHBOARD          │ │ 4. NATURAL LANGUAGE AI ASSISTANT  │
│ Spatial GIS maps, cross-domain risk   │ │ Natural language to FHIR API      │
│ scoring & correlation heatmaps        │ │ query generator & risk summaries  │
└───────────────────────────────────────┘ └───────────────────────────────────┘
```

---

## Core HL7 FHIR Profiles & Data Model Mapping

| OAH Profile Name | Profile Target & System | Key Elements & Coding |
| :--- | :--- | :--- |
| **`location-oah`** | River stations & pilot study sites (Coimbra, Oslo, Benevento, Ghent, Toulouse) | GIS lat/lon coordinates, SNOMED CT (`420531007` for River), location URIs |
| **`observation-indicators-oah`** | Qualitative citizen field surveys | Hydrology/water flow, water appearance (clarity, foam, odor), riparian vegetation cover (trees >3m), invasive species |
| **`observation-with-component-oah`** | Quantitative physical/chemical lab & sensor metrics | Slices for **Average**, **Minimum**, **Maximum**, **Median**, and **Standard Deviation**; UCUM units (`mg/L`, `pH`); parameters: pH, Nitrate, Zinc, Cadmium |
| **`observation-health-measure-oah`** | Population health & epidemiological indicators | Chronic disease prevalence, diabetes treatment rates for nearby urban communities |
| **`Group`** | Demographic target cohorts | Cohorts by sex, age range (e.g. 18–29, 35–74), and location mapping |

---

## Phased Implementation Roadmap

### Phase 1: Data Ingestion & FHIR Adapter Pipeline (Days 1–3)
- [x] **Data Schema Definition**: Map raw IoT sensor JSON/CSV and citizen science app entries to FHIR OAH IG schemas.
- [x] **Unit & Code Standardization**: Implement UCUM unit mapping (`mg/L`, `pH`) and code system bindings (`temporarySystem-oah-eu`, SNOMED CT).
- [x] **Adapter Pipeline Script**: Build a Python ETL pipeline that validates raw payloads and constructs compliant FHIR JSON resources.
- [x] **RESTful Sandbox Transmitter**: Connect to the HAPI FHIR sandbox (`http://hapi.fhir.org/baseR4`) and implement HTTP `POST` requests for `/Location` and `/Observation`.

### Phase 2: Repository Integration & HAPI Sandbox Testing (Days 4–5)
- [x] **FHIR Server Validation**: Test HTTP `201 Created` / `200 OK` response codes and verify resource persistence on the test server.
- [x] **Resource Querying & Filtering**: Implement FHIR `GET` searches using parameters like `_profile`, `subject`, and `code`.

### Phase 3: One Health Correlation Dashboard (Days 6–9)
- [x] **Web Interface Setup**: Build an interactive web frontend (Streamlit / React / Plotly).
- [x] **Spatial GIS Mapping**: Plot `location-oah` river reaches with stream degradation heatmaps.
- [x] **Cross-Domain Correlation Engine**: Cross-reference chemical pollution spikes (`observation-with-component-oah`) against population health indicators (`observation-health-measure-oah`) for nearby demographic groups (`Group`).

### Phase 4: Conversational AI Query Assistant (Days 10–12)
- [x] **Natural Language to FHIR Translator**: Implement an AI agent that translates plain-English questions (e.g., *"Show me stations in Coimbra where nitrate exceeds safety thresholds"*) into valid FHIR REST URLs (`GET /Observation?_profile=...`).
- [x] **Automated Risk Briefings**: Parse returned FHIR JSON bundles and synthesize readable One Health intelligence reports for non-technical stakeholders.

---

## Submission & Demo Strategy (Winning Pitch)

### 1. Code Repository
- Fully documented GitHub repository containing the ETL adapter, dashboard frontend, and AI assistant code.
- Sample raw datasets and pre-configured FHIR JSON templates for instant reproduction.

### 2. Demo Video (3–5 Minutes Flow)
1. **The Problem (30s)**: Highlighting the disconnect between urban stream health and human public health data.
2. **Data Adapter Live Action (60s)**: Demonstrating raw IoT/citizen data being converted into FHIR OAH JSON payloads and posted to the sandbox.
3. **One Health Dashboard (90s)**: Showing the interactive map and cross-domain correlation charts between water pollution and chronic health measures.
4. **AI Assistant Demo (60s)**: Querying the FHIR server in natural language to receive instant, actionable environmental risk alerts.

---

*Project aligned with the OneAquaHealth IEEE Global Hackathon 2026 - Track 7: Digital Health Standards.*
