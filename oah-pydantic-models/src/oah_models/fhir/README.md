# `oah_models.fhir` — OAH → FHIR mapper

This subpackage turns the 7 OAH Pydantic models (`oah_models.*`) into FHIR R4
resources that conform to the OAH profiles in the `oah` IG
(`oah/input/fsh/profiles/*.fsh`). It is an **executable implementation** of
the 7 `ConceptMap` resources the IG already declares but never runs:
`oah/input/fsh/model-maps/*2FHIR.fsh`.

Nothing in here invents a mapping that isn't declared in one of those 7
files. Where a ConceptMap element is genuinely underspecified or the source
data has no way to satisfy a required target field, that's documented as a
gap below — not silently worked around.

## Files

| File | What's in it |
|---|---|
| `resources.py` | Minimal FHIR R4 resource shapes for the 4 profiles actually produced: `Location`, `Specimen`, `Observation`, `Library`. Uses real FHIR choice-type serialization (`valueQuantity`/`valueCodeableConcept`/`effectiveDateTime`/`effectivePeriod`, not a Python `Union` field). Also defines the canonical profile/extension/code-system URLs used throughout `mappers.py`. |
| `codes.py` | Field-name → display-text lookups for the `Observation.code` of every leaf in `HealthIndicatorsOah` and the `Base`-typed leaves of `IndicatorsOah`. Also documents two defects found in the source ConceptMap while building this (see [Known spec issues](#known-spec-issues-not-introduced-here)). |
| `mappers.py` | The actual mapping functions — one per ConceptMap. Each function's docstring lists the exact source→target element pairs it implements, so you can check it against the corresponding `*2FHIR.fsh` file line by line. |
| `__init__.py` | Re-exports the 7 mapper functions plus the resource classes, so `from oah_models.fhir import ...` is enough for normal use. |

## Coverage: which model maps to which function

| # | OAH model | Function | ConceptMap file | Returns |
|---|---|---|---|---|
| 1 | `SampleOah` | `sample_to_fhir(sample)` | `SampleOah2FHIR.fsh` | `(Location, Specimen)` |
| 2 | `SimpleIndicatorOah` | `simple_indicator_to_fhir(ind)` | `SimpleIndicatorOah2FHIR.fsh` | `(Observation, Location, Specimen)` |
| 3 | `StructuredIndicatorOah` | `structured_indicator_to_fhir(ind)` | `StructuredIndicatorOah2FHIR.fsh` | `(Observation, Location, Specimen)` |
| 4 | `HealthMeasureOah` | `health_measure_to_fhir(hm)` | `HealthMeasureOah2FHIR.fsh` | `(Observation, Location)` |
| 5 | `HealthIndicatorsOah` | `health_indicators_to_fhir(hi)` | `HealthIndicatorsOah2FHIR.fsh` | `List[(Observation, Location)]` |
| 6 | `IndicatorsOah` | `indicators_to_fhir(indicators, subject=None)` | `IndicatorsOah2FHIR.fsh` | `(sample_based, generic_based)` |
| 7 | `DataSetOah` | `dataset_to_fhir(ds)` | `DataSetOah2FHIR.fsh` | `Library` |

5 of 7 are complete against their ConceptMap. `DataSetOah` and `IndicatorsOah`
have documented, intentional gaps — see below.

## How to use it

### Install

```bash
cd oah-pydantic-models
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # pydantic>=2,<3
```

### Basic pattern: build an OAH instance, pass it to the matching function

```python
from oah_models import SampleOah
from oah_models.sample import SampleSite
from oah_models.common import Identifier, Gps
from oah_models.fhir import sample_to_fhir, simple_indicator_to_fhir

sample = SampleOah(
    site=SampleSite(
        identifier=[Identifier(value="benevento-01")],
        name=["Benevento site 01"],
        gps=Gps(longitude=14.781, latitude=41.129),
    ),
    dateOfSampling="2018-01-01T00:00:00",
)

location, specimen = sample_to_fhir(sample)
print(location.model_dump_json(indent=2, exclude_none=True))
print(specimen.model_dump_json(indent=2, exclude_none=True))
```

`simple_indicator_to_fhir`/`structured_indicator_to_fhir` build their own
`Location`/`Specimen` internally (from the indicator's `sampleDetails`), so
you don't need to call `sample_to_fhir` separately for those:

```python
observation, location, specimen = simple_indicator_to_fhir(indicator)
```

### `indicators_to_fhir` needs a `subject` for its generic leaves

`IndicatorsOah`'s water/hydromorphological/bioRisk/remote leaves
(`GenericIndicatorMeasure`) carry no site of their own, so their resulting
`Observation`s have no `subject` unless you pass one in:

```python
from oah_models.fhir.resources import FHIRReference

sample_based, generic_based = indicators_to_fhir(
    indicators, subject=FHIRReference(reference=f"Location/{location.id}")
)
```

`sample_based` (from the `SimpleIndicator`/`StructuredIndicator` leaves) is a
`List[(Observation, Location, Specimen)]`; `generic_based` is a plain
`List[Observation]`.

### De-duplicate `Location`/`Specimen` across multiple indicators from the same sample

Because `sample_to_fhir` derives `Location`/`Specimen` ids deterministically
from the sample's site identifier, calling any of the indicator-mapping
functions repeatedly for the same physical sample produces resources with the
**same `id`** each time — dedupe by `(resourceType, id)` before sending
anywhere:

```python
resources = {}
for ind in list_of_simple_indicators:
    obs, loc, spec = simple_indicator_to_fhir(ind)
    resources[("Observation", obs.id)] = obs
    resources[("Location", loc.id)] = loc
    resources[("Specimen", spec.id)] = spec

fhir_json_array = [r.model_dump(exclude_none=True) for r in resources.values()]
```

### `health_indicators_to_fhir` / `dataset_to_fhir` are one-shot

```python
from oah_models.fhir import health_indicators_to_fhir, dataset_to_fhir

pairs = health_indicators_to_fhir(health_indicators)   # List[(Observation, Location)]
library = dataset_to_fhir(dataset)                      # Library
```

### Run the smoke test

```bash
python examples/build_fhir_examples.py
```

This pipes the same Benevento example data from `examples/build_examples.py`
through every mapper function and prints the resulting FHIR JSON.

## Known spec issues (not introduced here)

Found while implementing this against the actual `*2FHIR.fsh` files, and
worth knowing about before trusting the output against a terminology server:

1. **`morphology`/`landUse` code mismatch.** `IndicatorsOah2FHIR.fsh` states
   the code for these leaves should be the plain field name (`'morphology'`,
   `'landUse'`), but `oah-codeSystem.fsh` defines `morophology` (typo) and
   `LandUse` (capitalized) instead — neither matches what the ConceptMap
   says. This mapper follows the ConceptMap (the actual mapping spec), so the
   resulting code won't resolve against `TemporaryOahSystem` as currently
   defined. Fixing the mismatch belongs in the `oah` IG repo, not here.
2. **`remote.*` copy-paste bug.** All 29 `remote.*` leaves in
   `IndicatorsOah2FHIR.fsh` have their comment copied from
   `bioRisk.amphibians` and never updated — literally `"where
   Observation.code is 'amphibians'"` on every one. This mapper uses each
   leaf's own field name instead, consistent with every correctly-written
   leaf in the same file, rather than reproducing that bug.

## What's deliberately not mapped

- **`DataSet.record.format → DataRequirement.type`/`.profile`** — declared in
  `DataSetOah2FHIR.fsh` ("As FHIR resource" / "As FHIR profile") but with no
  rule for turning a free-text format string into a FHIR resource type or
  profile canonical. Left out of `dataset_to_fhir`.
- **`Sample.site.characteristics`** and **`Sample.site` (for `Specimen`)** —
  declared `relatedto` the target resource as a whole, not any specific
  field, in both `SampleOah2FHIR.fsh` and `HealthMeasureOah2FHIR.fsh`.
  Nothing is synthesized for them.
- **A `Group` resource for `HealthMeasure.cohort`** — `cohort` is already a
  `Reference` on `HealthMeasureOah`, so the mapper assumes the `Group` it
  points to exists elsewhere; nothing here constructs one from
  `GroupOah`/`group-oah.fsh`.
- **A `Bundle` wrapper** — every function returns loose resource objects, not
  a `Bundle`. Not yet built; ask if you want it.

## How to extend this module

- **Add a `Bundle` helper.** A `to_bundle(resources) -> dict` that dedupes by
  `(resourceType, id)` and wraps everything as `{"resourceType": "Bundle",
  "type": "collection", "entry": [...]}` would remove the manual dedup step
  shown above.
- **Add real code validation.** `codes.py`'s displays are static text; if you
  need to confirm a code actually exists in `TemporaryOahSystem`, you'd parse
  `oah/input/fsh/terminologies/oah-codeSystem.fsh` (or its compiled
  `CodeSystem` JSON, once SUSHI has run) and check membership before trusting
  a mapper's output.
- **Add the `Group` mapping.** If you need to *construct* `GroupOah`
  resources (not just reference existing ones), model
  `input/fsh/profiles/group-oah.fsh`'s `characteristic` slices as a new
  resource class in `resources.py` and a `cohort_to_fhir` function in
  `mappers.py`.
- **Wire up a code-mapping layer for arbitrary input data.** Everything here
  maps *already-typed* OAH model instances to FHIR. Turning an arbitrary
  public-data column name into one of these OAH codes in the first place is
  a separate, upstream concern — see "Gaps" in `oah/REUSE-GUIDE.md`.
