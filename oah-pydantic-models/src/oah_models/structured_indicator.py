"""Structured Indicator model.

Source: oah/input/fsh/model-maps/StructuredIndicatorOah.fsh
Maps to (via StructuredIndicatorOah2FHIR.fsh): observation-with-component-oah.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Union

from pydantic import BaseModel, Field

from .common import CodeableConcept, Quantity, Reference
from .sample import SampleOah


class StructuredIndicatorComponent(BaseModel):
    """`StructuredIndicator.component` (1..*) -- one named sub-measure (e.g. average, max, min, stdev, median)."""

    type: CodeableConcept = Field(..., description="1..1. What this component measures.")
    result: Union[CodeableConcept, Quantity, str] = Field(..., description="1..1. Result of this component.")


class StructuredIndicatorOah(BaseModel):
    """An indicator composed of multiple named components (e.g. pollutant summary stats, macrophyte breakdown)."""

    sampleDetails: SampleOah = Field(..., description="1..1. The sample this indicator was measured on.")
    type: CodeableConcept = Field(..., description="1..1. What is measured overall.")
    date: List[datetime] = Field(..., description="1..*. Observation date(s).")
    performer: List[Reference] = Field(
        ..., description="1..*. Reference(PractitionerRole|Organization) who made the measurement."
    )
    component: List[StructuredIndicatorComponent] = Field(..., description="1..*. Component results.")
