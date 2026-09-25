"""Sample model.

Source: oah/input/fsh/model-maps/SampleOah.fsh
Maps to (via SampleOah2FHIR.fsh): LocationOah, SpecimenOah, observation-indicators-oah.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .common import Gps, Identifier, Reference


class SampleSite(BaseModel):
    """`Sample.site` (1..1) -- the sampling location and its metadata."""

    identifier: List[Identifier] = Field(..., description="1..*. Site identifier(s).")
    name: List[str] = Field(..., description="1..*. Site name(s).")
    gps: Optional[Gps] = Field(None, description="0..1. GPS position of the site.")
    characteristics: List[str] = Field(default_factory=list, description="0..*. Free-text site characteristics.")
    formReference: List[Reference] = Field(
        default_factory=list,
        description="0..*. Reference(Binary|QuestionnaireResponse|DocumentReference) with supporting details.",
    )


class SampleOah(BaseModel):
    """Sample: the sampling site and event supporting one or more indicators."""

    site: SampleSite = Field(..., description="1..1. Sampling site.")
    dateOfSampling: datetime = Field(..., description="1..1. Date of the sampling event.")
    performer: List[Reference] = Field(
        default_factory=list,
        description="0..*. Reference(PractitionerRole|Organization) that performed the sampling.",
    )
