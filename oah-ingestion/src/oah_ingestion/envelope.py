"""Shared event envelope and stream-specific payload validation."""

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PILOT_CITIES = {"coimbra", "oslo", "benevento", "ghent", "toulouse"}


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
            if measurement.parameter in {"nitrate", "zinc_dissolved", "cadmium_dissolved"} and measurement.value < 0.0:
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


class PublicHealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    health_agency: str = Field(min_length=1, max_length=250)
    evaluation_period: str = Field(min_length=1, max_length=100)
    cohort: Cohort
    risk_scores: list[RiskScore] = Field(min_length=1, max_length=500)
    chemical_summaries: list[ChemicalSummary] = Field(default_factory=list, max_length=500)


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


def print_generic_event(event: dict) -> None:
    """Print the normalized envelope as the current downstream handoff output."""
    import json

    print("\n--- Normalized ingestion event ---", flush=True)
    print(json.dumps(event, indent=2, ensure_ascii=False), flush=True)
