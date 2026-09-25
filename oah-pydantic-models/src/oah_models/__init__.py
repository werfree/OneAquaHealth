"""Pydantic models for the 7 OneAquaHealth (OAH) logical models.

Source of truth: the `oah` FHIR Implementation Guide repository, specifically
`input/fsh/model-maps/*.fsh`. See ../../README.md for how these map back to
that IG and what still needs to be built on top of them.
"""

from .dataset import DataSetOah, DataSetRecord
from .health_indicators import (
    CausesOfDeathGroup,
    DiseasePrevalenceGroup,
    HealthIndicatorsOah,
    HospitalizationGroup,
)
from .health_measure import HealthMeasureOah, HealthMeasureSite
from .indicators import (
    BioRiskIndicators,
    BiologicalIndicators,
    HydromorphologicalIndicators,
    IndicatorsOah,
    RemoteSensingIndicators,
    WaterIndicators,
)
from .sample import SampleOah, SampleSite
from .simple_indicator import SimpleIndicatorOah
from .structured_indicator import StructuredIndicatorComponent, StructuredIndicatorOah

__all__ = [
    "DataSetOah",
    "DataSetRecord",
    "IndicatorsOah",
    "BiologicalIndicators",
    "HydromorphologicalIndicators",
    "WaterIndicators",
    "BioRiskIndicators",
    "RemoteSensingIndicators",
    "HealthIndicatorsOah",
    "DiseasePrevalenceGroup",
    "CausesOfDeathGroup",
    "HospitalizationGroup",
    "HealthMeasureOah",
    "HealthMeasureSite",
    "SampleOah",
    "SampleSite",
    "SimpleIndicatorOah",
    "StructuredIndicatorOah",
    "StructuredIndicatorComponent",
]
