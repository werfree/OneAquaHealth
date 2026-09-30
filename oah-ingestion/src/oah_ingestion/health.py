"""Health-measure normalization using the OneAquaHealth logical models."""

import math
import re
import uuid
from datetime import date, datetime, time, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from oah_models import HealthMeasureOah, HealthMeasureSite
from oah_models.common import CodeableConcept, Coding, Identifier, Period, Quantity, Reference


OAH_CODE_SYSTEM = "http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu"
FHIR_ID_PATTERN = re.compile(r"^[A-Za-z0-9.-]{1,64}$")
MAX_RECORDS = 5000


class HealthMeasureInput(BaseModel):
    """Flat JSON/CSV row before conversion to the OAH logical model."""

    city: str = Field(min_length=1, max_length=100)
    site_id: str = Field(min_length=1, max_length=64)
    site_name: str = Field(min_length=1, max_length=200)
    period_start: date
    period_end: date
    indicator_code: str = Field(min_length=1, max_length=100)
    indicator_display: str = Field(min_length=1, max_length=250)
    value: float
    unit: str = Field(default="%", min_length=1, max_length=30)
    cohort_id: str = Field(min_length=1, max_length=64)
    cohort_display: str = Field(min_length=1, max_length=250)
    source_dataset: str = Field(min_length=1, max_length=250)
    source_publisher: Optional[str] = Field(default=None, max_length=250)

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("city cannot be blank")
        return value

    @field_validator("site_id", "cohort_id")
    @classmethod
    def validate_fhir_ids(cls, value: str) -> str:
        if not FHIR_ID_PATTERN.fullmatch(value):
            raise ValueError("must be a valid FHIR id (letters, digits, '.', '-'; max 64 chars)")
        return value

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("value must be a finite number")
        return value

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class HealthMeasureBatch(BaseModel):
    records: List[HealthMeasureInput] = Field(min_length=1, max_length=MAX_RECORDS)
    source_type: str = Field(default="HEALTH_DATA_MOCK", min_length=1, max_length=80)


def to_oah_health_measure(record: HealthMeasureInput) -> HealthMeasureOah:
    """Convert one normalized row to the repository's OAH Pydantic logical model."""
    period = Period(
        start=datetime.combine(record.period_start, time.min, tzinfo=timezone.utc),
        end=datetime.combine(record.period_end, time.max, tzinfo=timezone.utc),
    )
    return HealthMeasureOah(
        site=HealthMeasureSite(
            identifier=[Identifier(value=record.site_id)],
            name=[record.site_name],
        ),
        dateOrPeriod=period,
        type=CodeableConcept(
            coding=[Coding(
                system=OAH_CODE_SYSTEM,
                code=record.indicator_code,
                display=record.indicator_display,
            )]
        ),
        result=Quantity(
            value=record.value,
            unit=record.unit,
            system="http://unitsofmeasure.org",
            code=record.unit,
        ),
        cohort=Reference(
            reference=f"Group/{record.cohort_id}",
            display=record.cohort_display,
        ),
    )


def build_health_message(batch: HealthMeasureBatch) -> dict:
    """Wrap validated OAH logical measures in a transport event."""
    return {
        "event_id": str(uuid.uuid4()),
        "source_type": batch.source_type,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(batch.records),
        "records": [
            {
                "city": record.city,
                "source_dataset": record.source_dataset,
                "source_publisher": record.source_publisher,
                "oah_health_measure": to_oah_health_measure(record).model_dump(
                    mode="json", exclude_none=True
                ),
            }
            for record in batch.records
        ],
    }
