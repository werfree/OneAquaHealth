"""CSV parser for batch public-health input.

Each CSV row represents one risk score or chemical summary. Rows sharing an
event_id are assembled into one validated PUBLIC_HEALTH envelope before the
pipeline processes any events.
"""

from __future__ import annotations

import csv
import io
from collections import OrderedDict

from .envelope import PublicHealthEnvelope

CSV_TEMPLATE_COLUMNS = (
    "event_id",
    "city",
    "site_id",
    "timestamp",
    "received_at",
    "health_agency",
    "evaluation_period",
    "cohort_group_id",
    "cohort_age_range",
    "cohort_gender",
    "record_type",
    "indicator",
    "value",
    "unit",
    "interpretation",
)
REQUIRED_COLUMNS = set(CSV_TEMPLATE_COLUMNS)
METADATA_COLUMNS = (
    "city", "site_id", "timestamp", "received_at", "health_agency", "evaluation_period",
    "cohort_group_id", "cohort_age_range", "cohort_gender",
)


class CsvIngestionError(ValueError):
    """CSV is malformed or cannot be represented as public-health envelopes."""


def parse_public_health_csv(text: str) -> list[PublicHealthEnvelope]:
    """Parse long-form health CSV, grouping indicator rows by event_id."""

    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    headers = reader.fieldnames or []
    missing = sorted(REQUIRED_COLUMNS - set(headers))
    if missing:
        raise CsvIngestionError(f"Missing required CSV columns: {', '.join(missing)}")
    if len(headers) != len(set(headers)):
        raise CsvIngestionError("CSV column names must be unique")

    events: OrderedDict[str, dict] = OrderedDict()
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise CsvIngestionError(f"Row {row_number} has more values than the header")
        if not row or all(value is None or not value.strip() for value in row.values()):
            continue
        cleaned = {key: (value or "").strip() for key, value in row.items()}
        event_id = cleaned["event_id"]
        if not event_id:
            raise CsvIngestionError(f"Row {row_number}: event_id is required")

        metadata = {key: cleaned[key] for key in METADATA_COLUMNS}
        event = events.setdefault(
            event_id,
            {
                "metadata": metadata,
                "risk_scores": [],
                "chemical_summaries": [],
                "first_row": row_number,
            },
        )
        if event["metadata"] != metadata:
            raise CsvIngestionError(f"Row {row_number}: metadata differs within event_id {event_id!r}")

        record_type = cleaned["record_type"]
        if record_type not in {"risk_score", "chemical_summary"}:
            raise CsvIngestionError(
                f"Row {row_number}: record_type must be 'risk_score' or 'chemical_summary'"
            )
        try:
            value = float(cleaned["value"])
        except ValueError as exc:
            raise CsvIngestionError(f"Row {row_number}: value must be numeric") from exc
        indicator = cleaned["indicator"]
        if not indicator:
            raise CsvIngestionError(f"Row {row_number}: indicator is required")

        if record_type == "risk_score":
            if not cleaned["interpretation"]:
                raise CsvIngestionError(f"Row {row_number}: risk_score requires interpretation")
            event["risk_scores"].append(
                {"indicator": indicator, "score": value, "interpretation": cleaned["interpretation"]}
            )
        else:
            if not cleaned["unit"]:
                raise CsvIngestionError(f"Row {row_number}: chemical_summary requires unit")
            if cleaned["interpretation"]:
                raise CsvIngestionError(f"Row {row_number}: chemical_summary must leave interpretation blank")
            event["chemical_summaries"].append(
                {"indicator": indicator, "value": value, "unit": cleaned["unit"]}
            )

    if not events:
        raise CsvIngestionError("CSV contains no data rows")

    envelopes = []
    for event_id, event in events.items():
        metadata = event["metadata"]
        try:
            envelopes.append(
                PublicHealthEnvelope.model_validate(
                    {
                        "event_id": event_id,
                        "source_type": "PUBLIC_HEALTH",
                        "city": metadata["city"],
                        "site_id": metadata["site_id"],
                        "timestamp": metadata["timestamp"],
                        **({"received_at": metadata["received_at"]} if metadata["received_at"] else {}),
                        "payload": {
                            "health_agency": metadata["health_agency"],
                            "evaluation_period": metadata["evaluation_period"],
                            "cohort": {
                                "group_id": metadata["cohort_group_id"],
                                "age_range": metadata["cohort_age_range"],
                                "gender": metadata["cohort_gender"],
                            },
                            "risk_scores": event["risk_scores"],
                            "chemical_summaries": event["chemical_summaries"],
                        },
                    }
                )
            )
        except Exception as exc:
            raise CsvIngestionError(
                f"Event {event_id!r} (starting row {event['first_row']}) failed envelope validation: {exc}"
            ) from exc
    return envelopes
