"""Simple Indicator model.

Source: oah/input/fsh/model-maps/SimpleIndicatorOah.fsh
Maps to (via SimpleIndicatorOah2FHIR.fsh): observation-indicators-oah.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Union

from pydantic import BaseModel, Field

from .common import CodeableConcept, Quantity, Reference
from .sample import SampleOah


class SimpleIndicatorOah(BaseModel):
    """An indicator represented by a single scalar/coded result (e.g. count of snails in a sample)."""

    sampleDetails: SampleOah = Field(..., description="1..1. The sample this indicator was measured on.")
    type: CodeableConcept = Field(..., description="1..1. What is measured, e.g. '% of people with Giardia'.")
    date: List[datetime] = Field(..., description="1..*. Observation date(s).")
    performer: List[Reference] = Field(
        ..., description="1..*. Reference(PractitionerRole|Organization) who made the measurement."
    )
    result: Union[CodeableConcept, Quantity] = Field(..., description="1..1. Result of the observation.")
