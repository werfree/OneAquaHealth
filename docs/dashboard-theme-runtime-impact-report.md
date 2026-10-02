# Dashboard theme and root-runtime update

**Date:** 2 October 2026
**Status:** Implemented and verified

## Executive summary

The dashboard now offers four appearance presets in the sidebar: **Aqua**, **Aqua dark**, **White**, and **Dark**. The server selects the featured default through `DASHBOARD_DEFAULT_THEME`; Aqua is the safe fallback. A valid user selection is retained in the browser and takes precedence over the server default on later visits.

Dashboard packaging and runtime configuration are now available from the repository root. The dashboard can be installed and started without changing into `dashboard/`, while the existing `dashboard/run.sh` and dashboard-local compatibility files continue to work.

## Feature update

### Theme selector

- Added an **Appearance** selector to the desktop sidebar and mobile bottom navigation.
- Added semantic color tokens for four complete themes, including surfaces, fields, graphs, notices, code blocks, navigation, and report views.
- Added `GET /api/config`, which returns only the public theme catalogue and selected default.
- Injected the validated default theme into the initial HTML so the server preset is present before the application bootstraps.
- Added browser persistence under the non-sensitive `oah-theme` preference key.
- Kept the theme independent of persona changes, station selection, navigation, ingestion state, and report state.

Supported configuration values:

| Value | Label | Color mode |
|---|---|---|
| `aqua` | Aqua | Light |
| `aqua-dark` | Aqua dark | Dark |
| `white` | White | Light |
| `dark` | Dark | Dark |

Invalid or missing `DASHBOARD_DEFAULT_THEME` values fail safely to `aqua`.

### Root-level runtime

The new root `pyproject.toml` defines:

- the dashboard's Python version and runtime dependencies;
- a `dev` dependency group for tests;
- static assets and mock fixture package data;
- the `oah-dashboard` command;
- the root pytest configuration.

The root `.env.example` documents all dashboard runtime variables. The root `.env` is loaded by the server and remains ignored by Git.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # only when a root .env does not already exist
oah-dashboard
```

The module entry point is also supported:

```bash
python3 -m dashboard.server
```

Root environment keys:

| Key | Default | Purpose |
|---|---|---|
| `APP_PORT` | `8000` | Existing OneAquaHealth API port |
| `DASHBOARD_PORT` | `8090` | Dashboard listen port |
| `OAH_LIVE_BASE_URL` | `http://127.0.0.1:8000` | Existing live gateway used by the dashboard proxy |
| `DASHBOARD_DEFAULT_THEME` | `aqua` | Featured theme for users without a saved preference |

## Runtime flow

```text
root .env
   │
   ▼
dashboard.server validates DASHBOARD_DEFAULT_THEME
   ├── injects the default into the initial HTML
   └── exposes the public /api/config response
                │
                ▼
          app bootstrap
                │
                ├── applies a valid saved user preference, if present
                └── otherwise applies the server default
```

## Impact analysis

| Area | Change | Impact | Risk and mitigation |
|---|---|---|---|
| Server startup | Added root environment loading and `main()` entry point | Dashboard starts from the repository root or installed console script | Environment values are validated; unsupported themes fall back to Aqua |
| Public API | Added `GET /api/config` | UI receives the allow-listed theme catalogue and default | The endpoint exposes no secrets or arbitrary environment values |
| Initial document | Server injects the default theme identifier | Correct server preset is available before application bootstrap | Replacement is limited to a fixed placeholder and a validated identifier |
| Client bootstrap | Configuration joins session and summary loading | Theme state is initialized with existing session data | Domain API payloads and role capability logic are unchanged |
| Client state | Added `theme` and `themeConfig` | Appearance is tracked separately from domain data | Only a theme identifier is stored; no health or user data enters browser storage |
| CSS | Replaced fixed presentation colors with semantic tokens | All existing views can render in four palettes | Visual checks covered overview, relationship graph, reports, desktop, and mobile |
| Mobile navigation | Added the theme control to the compact sidebar grid | Theme switching remains reachable at phone width | Verified at 390×844 with no horizontal overflow |
| Packaging | Added root `pyproject.toml` and package data | Installation and launch no longer depend on the dashboard directory | Dashboard-local requirements and launcher now delegate to the root configuration |
| Existing workflows | Preserved `dashboard/run.sh` and dashboard-local setup references | Existing developer commands remain usable | Compatibility files contain no second dependency list to drift |

### Code-path impact

The client `bootstrap()` function is the highest-impact integration point because it already fans out into session, summary, station, run, report, and render flows. Theme configuration was added to its initial fetch without changing those downstream domain calls. Theme updates only mutate document presentation attributes and theme-specific client state.

The server change is isolated to configuration, initial HTML delivery, and process startup. Ingestion, FHIR conversion, evidence retrieval, role capabilities, graph construction, report generation, and report download contracts are unchanged.

### Compatibility and precedence

1. A valid saved browser preference wins.
2. Otherwise, the validated `DASHBOARD_DEFAULT_THEME` value wins.
3. Missing or invalid configuration resolves to `aqua`.

This means changing the server default affects new users and users who have not selected a theme; it intentionally does not overwrite an existing personal preference.

## Files updated

- Root operations: `pyproject.toml`, `.env.example`, `.env`, `README.md`
- Server/package: `dashboard/__init__.py`, `dashboard/server.py`, `dashboard/run.sh`, `dashboard/requirements.txt`, `dashboard/.env.example`
- UI: `dashboard/static/index.html`, `dashboard/static/styles.css`, `dashboard/static/js/api.js`, `dashboard/static/js/app.js`, `dashboard/static/js/state.js`
- Documentation/tests: `dashboard/README.md`, `dashboard/API-MAPPING.md`, `dashboard/tests/test_server.py`

No ingestion, FHIR-model, agent, publisher, or infrastructure implementation was changed for these two features.

## Verification results

| Check | Result |
|---|---|
| Root `python3 -m pytest` | 6 passed |
| Python bytecode compilation | Passed |
| JavaScript syntax checks | Passed |
| `git diff --check` | Passed |
| Root `python3 -m dashboard.server` launch | Passed on an isolated verification port |
| Server default: valid value | `white` resolved to `white` |
| Server default: invalid value | Fell back to `aqua` |
| Four theme options | Present and selectable |
| Theme persistence | `dark` remained selected after reload |
| Role/theme independence | `dark` remained selected after switching from Analyst to Viewer |
| Relationship graph regression | Visible with 8 graph nodes |
| Reports regression | Existing report, generation, and download controls present |
| Mobile 390×844 | Selector visible; no horizontal overflow |
| Browser console | No warnings or errors |

## Operational notes

- The default theme is a deployment preset, not an enforced policy.
- Theme selection is browser-local and contains no sensitive data.
- The dashboard remains mock-first. Root packaging does not merge or replace the separate editable packages used by the full ingestion stack in `requirements.txt`.
- Restart the dashboard process after changing root `.env` values.
