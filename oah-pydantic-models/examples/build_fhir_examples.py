"""Pipe every OAH model through its mapper and print the resulting FHIR R4 JSON.

This is the smoke test `src/oah_models/fhir/README.md` refers to. It reuses the
Benevento example data from `build_examples.py` so the two stay in step.

Run with:
    pip install -r requirements.txt
    python examples/build_fhir_examples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_examples import (  # noqa: E402
    build_dataset,
    build_health_indicators,
    build_health_measure,
    build_indicators,
    build_sample,
    build_simple_indicator,
    build_structured_indicator,
)

from oah_models.fhir import (  # noqa: E402
    dataset_to_fhir,
    health_indicators_to_fhir,
    health_measure_to_fhir,
    indicators_to_fhir,
    sample_to_fhir,
    simple_indicator_to_fhir,
    structured_indicator_to_fhir,
)
from oah_models.fhir.resources import FHIRReference  # noqa: E402


def show(label: str, *resources) -> None:
    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")
    for resource in resources:
        print(f"--- {resource.resourceType}/{resource.id} ---")
        print(resource.model_dump_json(indent=2, exclude_none=True))


def main() -> None:
    sample = build_sample()

    # 1. SampleOah -> (Location, Specimen)
    location, specimen = sample_to_fhir(sample)
    show("1. SampleOah2FHIR.fsh  ->  Location + Specimen", location, specimen)

    # 2. SimpleIndicatorOah -> observation-indicators-oah
    obs, _, _ = simple_indicator_to_fhir(build_simple_indicator(sample))
    show("2. SimpleIndicatorOah2FHIR.fsh  ->  Observation", obs)

    # 3. StructuredIndicatorOah -> observation-with-component-oah
    obs, _, _ = structured_indicator_to_fhir(build_structured_indicator(sample))
    show("3. StructuredIndicatorOah2FHIR.fsh  ->  Observation", obs)

    # 4. HealthMeasureOah -> observation-health-measure-oah
    obs, loc = health_measure_to_fhir(build_health_measure())
    show("4. HealthMeasureOah2FHIR.fsh  ->  Observation + Location", obs, loc)

    # 5. HealthIndicatorsOah -> many Observations
    pairs = health_indicators_to_fhir(build_health_indicators())
    show(f"5. HealthIndicatorsOah2FHIR.fsh  ->  {len(pairs)} Observation(s)", *[o for o, _ in pairs])

    # 6. IndicatorsOah -> sample-based + generic Observations
    sample_based, generic = indicators_to_fhir(
        build_indicators(sample), subject=FHIRReference(reference=f"Location/{location.id}")
    )
    show(
        f"6. IndicatorsOah2FHIR.fsh  ->  {len(sample_based)} sample-based, {len(generic)} generic",
        *[o for o, _, _ in sample_based],
        *generic,
    )

    # 7. DataSetOah -> LibraryOah
    show("7. DataSetOah2FHIR.fsh  ->  Library", dataset_to_fhir(build_dataset()))

    print(f"\n{'=' * 78}\nAll 7 ConceptMaps executed successfully.\n{'=' * 78}")


if __name__ == "__main__":
    main()
