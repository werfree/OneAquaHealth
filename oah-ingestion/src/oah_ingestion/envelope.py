"""Shared event envelope and stream-specific payload validation."""

import os
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Cities in the current deployment. Set OAH_CITIES to a comma-separated list
# to run the pipeline somewhere else without editing code.
PILOT_CITIES = {
    c.strip().lower()
    for c in os.getenv("OAH_CITIES", "coimbra,oslo,benevento,ghent,toulouse,delhi,kanpur,varanasi,mumbai,chennai,hyderabad").split(",")
    if c.strip()
}


class EnvelopeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    city: str
    site_id: str = Field(min_length=1, max_length=64)
    timestamp: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in PILOT_CITIES:
            raise ValueError(f"city must be one of: {', '.join(sorted(PILOT_CITIES))}")
        return normalized

    @field_validator("timestamp", "received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp fields must include a timezone")
        return value.astimezone(timezone.utc)


# Parameters where a negative reading is physically meaningful; everything else
# is a concentration or a count and cannot be below zero.
MAY_BE_NEGATIVE = {"water_temperature", "temperature", "air_temperature", "redox_potential", "orp"}


class QuantitativeMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=30)
    value: float = Field(allow_inf_nan=False)
    min_value: Optional[float] = Field(default=None, allow_inf_nan=False)
    max_value: Optional[float] = Field(default=None, allow_inf_nan=False)
    avg_value: Optional[float] = Field(default=None, allow_inf_nan=False)


class IoTPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=100)
    measurements: list[QuantitativeMeasurement] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_measurement_ranges(self):
        for measurement in self.measurements:
            if measurement.parameter == "ph" and not 0.0 <= measurement.value <= 14.0:
                raise ValueError("ph measurements must be between 0 and 14")
            if measurement.parameter not in MAY_BE_NEGATIVE and measurement.value < 0.0:
                raise ValueError(f"{measurement.parameter} measurements cannot be negative")
        return self


class IoTEnvelope(EnvelopeBase):
    source_type: Literal["IOT_TELEMETRY"]
    payload: IoTPayload


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class SurveyObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str = Field(min_length=1, max_length=100)
    value_code: str = Field(min_length=1, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=2000)


class CitizenSurveyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(min_length=1, max_length=100)
    volunteer_id: str = Field(min_length=1, max_length=100)
    coordinates: Coordinates
    observations: list[SurveyObservation] = Field(min_length=1, max_length=500)
    photo_urls: list[str] = Field(default_factory=list, max_length=100)


class CitizenSurveyEnvelope(EnvelopeBase):
    source_type: Literal["CITIZEN_SURVEY"]
    payload: CitizenSurveyPayload


class Cohort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str = Field(min_length=1, max_length=64)
    age_range: str = Field(min_length=1, max_length=30)
    gender: str = Field(min_length=1, max_length=30)


class RiskScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str = Field(min_length=1, max_length=100)
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    interpretation: Literal["LOW", "MODERATE", "HIGH"]


class ChemicalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str = Field(min_length=1, max_length=100)
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=30)


class DiseaseSurveillance(BaseModel):
    """One IDSP/IHIP syndromic surveillance line for a reporting period.

    IDSP reports case counts against a catchment population, not a normalized
    score, so the rate is carried explicitly rather than derived downstream
    where the denominator would be lost.
    """

    model_config = ConfigDict(extra="forbid")

    condition: str = Field(min_length=1, max_length=100, description="e.g. acute_diarrhoeal_disease, cholera")
    cases: int = Field(ge=0, le=10_000_000)
    population_at_risk: int = Field(gt=0, le=2_000_000_000)
    rate_per_100k: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    baseline_rate_per_100k: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def derive_rate(self):
        if self.rate_per_100k is None:
            object.__setattr__(self, "rate_per_100k", round(self.cases / self.population_at_risk * 100_000, 2))
        return self


class PublicHealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    health_agency: str = Field(min_length=1, max_length=250)
    evaluation_period: str = Field(min_length=1, max_length=100)
    cohort: Cohort
    risk_scores: list[RiskScore] = Field(default_factory=list, max_length=500)
    chemical_summaries: list[ChemicalSummary] = Field(default_factory=list, max_length=500)
    disease_surveillance: list[DiseaseSurveillance] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def require_some_content(self):
        if not (self.risk_scores or self.disease_surveillance or self.chemical_summaries):
            raise ValueError("a public-health event must carry risk scores, surveillance lines or chemistry")
        return self


class PublicHealthEnvelope(EnvelopeBase):
    source_type: Literal["PUBLIC_HEALTH"]
    payload: PublicHealthPayload


IngestionEnvelope = Annotated[
    Union[IoTEnvelope, CitizenSurveyEnvelope, PublicHealthEnvelope],
    Field(discriminator="source_type"),
]


def envelope_as_message(envelope: IngestionEnvelope) -> dict:
    """Normalize the event and stamp gateway-owned metadata."""
    from uuid import uuid4

    message = envelope.model_dump(mode="json")
    message["event_id"] = str(uuid4())
    message["received_at"] = datetime.now(timezone.utc).isoformat()
    return message
