"""Minimal FHIR R4 resource shapes for the OAH profiles.

Not a general-purpose FHIR library -- just enough structure to hold data that
conforms to the specific OAH profiles in oah/input/fsh/profiles/*.fsh, using
real FHIR JSON serialization conventions (choice-type fields serialize as
`value<Type>` / `effective<Type>` / `collected<Type>`, not a Python Union).

Profile canonical URLs mirror `sushi-config.yaml`'s `canonical` +
`input/fsh/profiles/*.fsh` `Id`s.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

OAH_CANONICAL_BASE = "http://hl7.eu/fhir/ig/oah"
LOCATION_PROFILE = f"{OAH_CANONICAL_BASE}/StructureDefinition/location-oah"
SPECIMEN_PROFILE = f"{OAH_CANONICAL_BASE}/StructureDefinition/specimen-oah"
OBSERVATION_INDICATORS_PROFILE = f"{OAH_CANONICAL_BASE}/StructureDefinition/observation-indicators-oah"
OBSERVATION_WITH_COMPONENT_PROFILE = f"{OAH_CANONICAL_BASE}/StructureDefinition/observation-with-component-oah"
OBSERVATION_HEALTH_MEASURE_PROFILE = f"{OAH_CANONICAL_BASE}/StructureDefinition/observation-health-measure-oah"
LIBRARY_PROFILE = f"{OAH_CANONICAL_BASE}/StructureDefinition/library-oah"
CODE_SYSTEM_URL = f"{OAH_CANONICAL_BASE}/CodeSystem/temporarySystem-oah-eu"

# Location.extension:referenceForm target, per SampleOah2FHIR.fsh
# (`Sample.site.formReference` -> `Location.extension:referenceForm`) and the
# `$artifact-relatedArtifact` alias in input/fsh/alias-extensions.fsh.
REFERENCE_FORM_EXTENSION_URL = "http://hl7.org/fhir/StructureDefinition/artifact-relatedArtifact"
LIBRARY_SIZE_EXTENSION_URL = f"{OAH_CANONICAL_BASE}/StructureDefinition/library-size"
LIBRARY_NUMBER_OF_RECORDS_EXTENSION_URL = f"{OAH_CANONICAL_BASE}/StructureDefinition/library-numberOfRecords"


class FHIRMeta(BaseModel):
    profile: List[str] = Field(default_factory=list)


class FHIRCoding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None


class FHIRCodeableConcept(BaseModel):
    coding: List[FHIRCoding] = Field(default_factory=list)
    text: Optional[str] = None


class FHIRQuantity(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    system: Optional[str] = None
    code: Optional[str] = None


class FHIRIdentifier(BaseModel):
    system: Optional[str] = None
    value: Optional[str] = None


class FHIRReference(BaseModel):
    reference: Optional[str] = None
    type: Optional[str] = None
    display: Optional[str] = None


class FHIRPeriod(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class FHIRPosition(BaseModel):
    longitude: float
    latitude: float
    altitude: Optional[float] = None


class FHIRContactPoint(BaseModel):
    system: Optional[str] = None
    value: Optional[str] = None


class FHIRContactDetail(BaseModel):
    name: Optional[str] = None
    telecom: List[FHIRContactPoint] = Field(default_factory=list)


class FHIRAttachment(BaseModel):
    """Used for `Library.content` (per DataSetOah2FHIR.fsh: `DataSet.record` -> `Library.content`)."""

    contentType: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    size: Optional[float] = None


class FHIRRelatedArtifact(BaseModel):
    """Minimal RelatedArtifact, used as `Location.extension:referenceForm`'s value."""

    type: Literal["documentation"] = "documentation"
    url: Optional[str] = None
    display: Optional[str] = None


class FHIRExtension(BaseModel):
    url: str
    valueQuantity: Optional[FHIRQuantity] = None
    valueInteger: Optional[int] = None
    valueRelatedArtifact: Optional[FHIRRelatedArtifact] = None


class Location(BaseModel):
    """Per `location-oah.fsh` + `SampleOah2FHIR.fsh` / `HealthMeasureOah2FHIR.fsh`."""

    resourceType: Literal["Location"] = "Location"
    id: Optional[str] = None
    meta: FHIRMeta = Field(default_factory=lambda: FHIRMeta(profile=[LOCATION_PROFILE]))
    extension: List[FHIRExtension] = Field(default_factory=list)
    identifier: List[FHIRIdentifier] = Field(default_factory=list)
    name: Optional[str] = None
    mode: Literal["instance"] = "instance"
    position: Optional[FHIRPosition] = None


class SpecimenCollection(BaseModel):
    collector: Optional[FHIRReference] = None
    collectedDateTime: Optional[str] = None


class Specimen(BaseModel):
    """Per `specimen-oah.fsh` + `SampleOah2FHIR.fsh`."""

    resourceType: Literal["Specimen"] = "Specimen"
    id: Optional[str] = None
    meta: FHIRMeta = Field(default_factory=lambda: FHIRMeta(profile=[SPECIMEN_PROFILE]))
    subject: Optional[FHIRReference] = None
    type: Optional[FHIRCodeableConcept] = None
    collection: Optional[SpecimenCollection] = None


class ObservationComponent(BaseModel):
    code: FHIRCodeableConcept
    valueQuantity: Optional[FHIRQuantity] = None
    valueCodeableConcept: Optional[FHIRCodeableConcept] = None
    valueString: Optional[str] = None


class Observation(BaseModel):
    """Per `observation-indicators-oah.fsh` / `observation-with-component.fsh` / `observation-health-measure-oah.fsh`."""

    resourceType: Literal["Observation"] = "Observation"
    id: Optional[str] = None
    meta: FHIRMeta
    status: str = "final"
    code: FHIRCodeableConcept
    subject: Optional[FHIRReference] = None
    focus: List[FHIRReference] = Field(default_factory=list)
    specimen: Optional[FHIRReference] = None
    effectiveDateTime: Optional[str] = None
    effectivePeriod: Optional[FHIRPeriod] = None
    performer: List[FHIRReference] = Field(default_factory=list)
    valueQuantity: Optional[FHIRQuantity] = None
    valueCodeableConcept: Optional[FHIRCodeableConcept] = None
    valueString: Optional[str] = None
    component: List[ObservationComponent] = Field(default_factory=list)


class Library(BaseModel):
    """Per `library-oah.fsh` + `DataSetOah2FHIR.fsh`."""

    resourceType: Literal["Library"] = "Library"
    id: Optional[str] = None
    meta: FHIRMeta = Field(default_factory=lambda: FHIRMeta(profile=[LIBRARY_PROFILE]))
    extension: List[FHIRExtension] = Field(default_factory=list)
    url: str
    identifier: List[FHIRIdentifier] = Field(default_factory=list)
    version: Optional[str] = None
    title: Optional[str] = None
    status: str = "draft"
    type: Optional[FHIRCodeableConcept] = None
    description: Optional[str] = None
    contact: List[FHIRContactDetail] = Field(default_factory=list)
    publisher: Optional[str] = None
    author: List[FHIRContactDetail] = Field(default_factory=list)
    date: Optional[str] = None
    copyright: Optional[str] = None
    approvalDate: Optional[str] = None
    lastReviewDate: Optional[str] = None
    content: List[FHIRAttachment] = Field(default_factory=list)
