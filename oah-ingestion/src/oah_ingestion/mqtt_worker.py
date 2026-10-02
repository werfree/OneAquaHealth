"""MQTT sensor stream worker used by the ingestion application."""

import logging
import os
import ssl
from uuid import uuid4

import paho.mqtt.client as mqtt

from .envelope import IoTEnvelope, envelope_as_message
from .pipeline import process
from .sensor import SensorIngestionService

logger = logging.getLogger("OAH_MQTT_Consumer")


def create_mqtt_client() -> mqtt.Client:
    """Create a configured client; callers own starting and stopping its loop."""
    client_id = os.getenv("MQTT_CLIENT_ID") or f"OAHIngest-{uuid4().hex[:10]}"
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
    )
    client.manual_ack_set(True)
    ingestion = SensorIngestionService()

    def on_connect(client, userdata, flags, reason_code, properties):
        del userdata, flags, properties
        if reason_code == 0:
            topic_filter = os.getenv("MQTT_TOPIC", "oneaquahealth/sensors/+/+")
            client.subscribe(topic_filter, qos=1)
            logger.info("Connected as MQTT client %s; subscribed to %s", client_id, topic_filter)
        else:
            logger.error("MQTT connection failed: %s", reason_code)

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        del client, userdata, disconnect_flags, properties
        if reason_code != 0:
            logger.warning("MQTT client %s disconnected: %s", client_id, reason_code)

    def on_message(client, userdata, message):
        del userdata
        try:
            result = ingestion.process_packet(message.topic, message.payload.decode("utf-8"))
            if result["status"] != "ACCEPTED":
                logger.warning("Rejected MQTT packet on %s: %s", message.topic, result["reason"])
                if message.qos > 0:
                    client.ack(message.mid, message.qos)
                return
            sensor_event = result["event"]
            envelope = IoTEnvelope.model_validate(
                {
                    "event_id": sensor_event["event_id"],
                    "source_type": "IOT_TELEMETRY",
                    "city": sensor_event["city"],
                    "site_id": sensor_event["site_id"],
                    "timestamp": sensor_event["timestamp"],
                    "received_at": sensor_event["received_at"],
                    "payload": {
                        "device_id": sensor_event["device_id"],
                        "measurements": sensor_event["measurements"],
                    },
                }
            )
            event = envelope_as_message(envelope)
            measurement_count = len(event["payload"]["measurements"])
            process(envelope, event)
            if message.qos > 0:
                client.ack(message.mid, message.qos)
            logger.info("Normalized sensor event %s (%d measurements)", event["event_id"], measurement_count)
        except Exception:
            logger.exception("Could not normalize MQTT packet on %s", message.topic)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    username, password = os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")
    if username and password:
        client.username_pw_set(username, password)
    if os.getenv("MQTT_TLS", "false").lower() == "true":
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    return client


def mqtt_broker_address() -> tuple[str, int]:
    return os.getenv("MQTT_HOST", "broker.hivemq.com"), int(os.getenv("MQTT_PORT", "1883"))
