"""Health Measure model.

Source: oah/input/fsh/model-maps/HealthMeasureOah.fsh
Maps to (via HealthMeasureOah2FHIR.fsh): GroupOah, observation-health-measure-oah.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from .common import CodeableConcept, Gps, Identifier, Period, Quantity, Reference


class HealthMeasureSite(BaseModel):
    """`HealthMeasure.site` (1..1) -- the sampling/observation site."""

    identifier: List[Identifier] = Field(..., description="1..*. Site identifier(s).")
    name: List[str] = Field(..., description="1..*. Site name(s).")
    gps: Optional[Gps] = Field(None, description="0..1. GPS position of the site.")
    characteristics: List[str] = Field(default_factory=list, description="0..*. Free-text site characteristics.")


class HealthMeasureOah(BaseModel):
    """A single health/wellness measurement for a cohort at a site (e.g. % of a district's population with a condition)."""

    site: HealthMeasureSite = Field(..., description="1..1. Sampling site.")
    dateOrPeriod: Union[datetime, Period] = Field(..., description="1..1. Measure date or period.")
    performer: List[Reference] = Field(
        default_factory=list,
        description="0..*. Reference(PractitionerRole|Organization) who performed the measurement.",
    )
    type: CodeableConcept = Field(..., description="1..1. What is measured, e.g. '% of people with Giardia'.")
    result: Union[CodeableConcept, Quantity] = Field(..., description="1..1. Result of the observation.")
    cohort: Reference = Field(..., description="1..1. Reference(Group) -- the population this measure describes.")
