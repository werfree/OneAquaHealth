"""Shared FHIR-ish datatypes reused across the OAH logical models.

These are simplified stand-ins for the FHIR R4 datatypes referenced by the
OneAquaHealth (OAH) logical models in `input/fsh/model-maps/*.fsh` (Identifier,
CodeableConcept, Quantity, ContactDetail, Period, Reference). They are not a
full FHIR datatype library -- just enough structure to hold OAH data before it
is serialized into real FHIR resources.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class Coding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None


class CodeableConcept(BaseModel):
    """A code (e.g. from `oah-codeSystem.fsh`) plus optional free text."""

    coding: List[Coding] = Field(default_factory=list)
    text: Optional[str] = None


class Quantity(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    system: Optional[str] = None
    code: Optional[str] = None


class Identifier(BaseModel):
    system: Optional[str] = None
    value: str


class Reference(BaseModel):
    """Generic reference to another resource (e.g. PractitionerRole, Organization, Group, Binary)."""

    reference: Optional[str] = None
    type: Optional[str] = None
    display: Optional[str] = None


class ContactDetail(BaseModel):
    name: Optional[str] = None
    telecom: List[str] = Field(default_factory=list)


class Period(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class Gps(BaseModel):
    """WGS84 coordinates. Mirrors `Sample.site.gps` in SampleOah.fsh."""

    longitude: float
    latitude: float
    altitude: Optional[float] = None


class GenericIndicatorMeasure(BaseModel):
    """Stand-in for elements typed `Base` in the source FSH.

    IndicatorsOah.fsh leaves several leaves (hydromorphological.*, water.*,
    bioRisk.*, remote.*, biological.microbiomes) typed as the abstract FHIR
    `Base` type, i.e. "not yet modeled in detail". This model keeps those
    values usable -- a scalar/coded result with optional unit, date and free
    text -- until the IG defines dedicated logical models for them.
    """

    value: Optional[Union[float, str, bool]] = None
    unit: Optional[str] = None
    date: Optional[datetime] = None
    notes: Optional[str] = None
