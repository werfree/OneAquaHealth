"""Sanity-check script: build one instance of each of the 7 OAH models.

Run with:
    pip install -r requirements.txt
    python examples/build_examples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oah_models import (  # noqa: E402
    CausesOfDeathGroup,
    DataSetOah,
    DiseasePrevalenceGroup,
    HealthIndicatorsOah,
    HealthMeasureOah,
    HospitalizationGroup,
    IndicatorsOah,
    SampleOah,
    SimpleIndicatorOah,
    StructuredIndicatorOah,
)
from oah_models.common import CodeableConcept, Coding, Gps, Identifier, Quantity, Reference
from oah_models.health_measure import HealthMeasureSite
from oah_models.indicators import BiologicalIndicators
from oah_models.sample import SampleSite
from oah_models.structured_indicator import StructuredIndicatorComponent


def build_sample() -> SampleOah:
    return SampleOah(
        site=SampleSite(
            identifier=[Identifier(system="https://oneaquahealth.eu/location-id", value="benevento-01")],
            name=["Benevento monitoring site 01"],
            gps=Gps(longitude=14.781, latitude=41.129),
        ),
        dateOfSampling="2018-01-01T00:00:00",
        performer=[Reference(reference="Organization/Org-ARPAC-Campania", display="ARPAC Campania")],
    )


def build_structured_indicator(sample: SampleOah) -> StructuredIndicatorOah:
    # Mirrors input/fsh/examples/benevento_pollutant_01.fsh (Benzene, 2018 summary).
    return StructuredIndicatorOah(
        sampleDetails=sample,
        type=CodeableConcept(coding=[Coding(system="https://oneaquahealth.eu/air-parameters", code="benzene", display="Benzene")]),
        date=["2018-01-01T00:00:00"],
        performer=sample.performer,
        component=[
            StructuredIndicatorComponent(
                type=CodeableConcept(coding=[Coding(code="average", display="Average")]),
                result=Quantity(value=1.54, unit="ug/m3"),
            ),
            StructuredIndicatorComponent(
                type=CodeableConcept(coding=[Coding(code="maximum", display="Maximum")]),
                result=Quantity(value=7.1, unit="ug/m3"),
            ),
        ],
    )


def build_simple_indicator(sample: SampleOah) -> SimpleIndicatorOah:
    return SimpleIndicatorOah(
        sampleDetails=sample,
        type=CodeableConcept(text="Benthic Macroinvertebrates count"),
        date=["2018-06-01T00:00:00"],
        performer=sample.performer,
        result=Quantity(value=12, unit="count"),
    )


def build_indicators(sample: SampleOah) -> IndicatorsOah:
    return IndicatorsOah(
        biological=BiologicalIndicators(macroinvertebreates=[build_simple_indicator(sample)])
    )


def build_health_measure() -> HealthMeasureOah:
    return HealthMeasureOah(
        site=HealthMeasureSite(identifier=[Identifier(value="benevento-district-1")], name=["Benevento"]),
        dateOrPeriod="2024-01-01T00:00:00",
        type=CodeableConcept(text="% of people with high blood pressure (prevalence)"),
        result=Quantity(value=23.5, unit="%"),
        cohort=Reference(reference="Group/Group-BN-Age-35-74"),
    )


def build_health_indicators() -> HealthIndicatorsOah:
    return HealthIndicatorsOah(
        diseasePrevalence=[DiseasePrevalenceGroup(highBloodPression=[build_health_measure()])],
        causesOfDeath=[CausesOfDeathGroup()],
        hospitalization=[HospitalizationGroup()],
    )


def build_dataset() -> DataSetOah:
    return DataSetOah(
        pid="https://oneaquahealth.eu/datasets/benevento-2018-2019",
        title="Benevento air-quality and disease prevalence 2018-2019",
        publisher="OneAquaHealth Project",
        numberOfRecords=24,
    )


def main() -> None:
    sample = build_sample()
    models = [
        sample,
        build_structured_indicator(sample),
        build_simple_indicator(sample),
        build_indicators(sample),
        build_health_measure(),
        build_health_indicators(),
        build_dataset(),
    ]
    for model in models:
        print(f"OK: {type(model).__name__}")
        print(model.model_dump_json(indent=2, exclude_none=True)[:300], "...\n")


if __name__ == "__main__":
    main()
