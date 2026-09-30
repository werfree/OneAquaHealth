"""Validation and RabbitMQ transport for MQTT sensor telemetry."""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


VALID_PILOT_CITIES = {"coimbra", "oslo", "benevento", "ghent", "toulouse"}
SENSOR_QUEUE = "sensor.telemetry"


class QuantitativeMeasurement(BaseModel):
    parameter: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=30)
    value: float = Field(allow_inf_nan=False)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None


class TelemetryPayload(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    city: str
    site_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    measurements: List[QuantitativeMeasurement] = Field(min_length=1, max_length=500)

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str) -> str:
        city = value.strip().lower()
        if city not in VALID_PILOT_CITIES:
            raise ValueError(f"city must be one of: {', '.join(sorted(VALID_PILOT_CITIES))}")
        return city

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(timezone.utc)


def _valid_measurement(measurement: QuantitativeMeasurement) -> bool:
    if measurement.parameter == "ph":
        return 0.0 <= measurement.value <= 14.0
    if measurement.parameter in {"nitrate", "zinc_dissolved", "cadmium_dissolved"}:
        return measurement.value >= 0.0
    return True


class SensorIngestionService:
    """Validate MQTT topic/payload agreement and build a normalized event."""

    def process_packet(self, topic: str, raw_json: str) -> Dict[str, Any]:
        try:
            parts = topic.split("/")
            if len(parts) != 4 or parts[:2] != ["oneaquahealth", "sensors"]:
                raise ValueError("topic must match oneaquahealth/sensors/{city}/{site_id}")
            payload = TelemetryPayload.model_validate_json(raw_json)
            if parts[2].lower() != payload.city or parts[3] != payload.site_id:
                raise ValueError("topic city/site_id must match payload city/site_id")
            measurements = [item.model_dump() for item in payload.measurements if _valid_measurement(item)]
            if not measurements:
                raise ValueError("packet contains no measurements within accepted ranges")
            event = {
                "event_id": str(uuid.uuid4()),
                "source_type": "MQTT_IOT_TELEMETRY",
                "topic": topic,
                "device_id": payload.device_id,
                "city": payload.city,
                "site_id": payload.site_id,
                "timestamp": payload.timestamp.isoformat(),
                "received_at": datetime.now(timezone.utc).isoformat(),
                "measurements": measurements,
            }
            return {"status": "ACCEPTED", "event": event}
        except Exception as exc:
            return {"status": "REJECTED", "reason": str(exc)}


def publish_sensor_event(event: Dict[str, Any]) -> None:
    """Publish one validated telemetry event durably and require broker confirmation."""
    try:
        import pika
    except ImportError as exc:
        raise RuntimeError("RabbitMQ support requires pika; install the project requirements") from exc

    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER", "oah"),
        os.getenv("RABBITMQ_PASSWORD", "oah-local-dev"),
    )
    parameters = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "localhost"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=30,
    )
    connection = pika.BlockingConnection(parameters)
    try:
        channel = connection.channel()
        channel.queue_declare(queue=SENSOR_QUEUE, durable=True)
        channel.confirm_delivery()
        confirmed = channel.basic_publish(
            exchange="",
            routing_key=SENSOR_QUEUE,
            body=json.dumps(event, separators=(",", ":")).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=pika.DeliveryMode.Persistent,
                message_id=event["event_id"],
            ),
            mandatory=True,
        )
        if not confirmed:
            raise RuntimeError("RabbitMQ did not confirm the sensor event")
    finally:
        connection.close()
