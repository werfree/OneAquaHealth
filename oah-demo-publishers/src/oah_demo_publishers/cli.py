"""Publish the three sample streams over their configured input channels."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import paho.mqtt.client as mqtt
import pika
from dotenv import load_dotenv

load_dotenv()

CITIZEN_SURVEY_QUEUE = "ingestion.citizen_surveys"


def _read_sample(sample_dir: Path, name: str) -> tuple[dict, bytes]:
    raw = (sample_dir / name).read_bytes()
    return json.loads(raw), raw


def publish_sensor_mqtt(sample_dir: Path) -> None:
    sample, raw = _read_sample(sample_dir, "sample_iot_telemetry_mqtt.json")
    host = os.getenv("MQTT_HOST", "broker.hivemq.com")
    port = int(os.getenv("MQTT_PORT", "1883"))
    topic = f"oneaquahealth/sensors/{sample['city']}/{sample['site_id']}"
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=os.getenv("MQTT_DEMO_CLIENT_ID", "OAH_Demo_Publisher"),
        protocol=mqtt.MQTTv5,
    )

    def on_connect(client, userdata, flags, reason_code, properties):
        del client, userdata, flags, properties
        print(f"MQTT: broker connection result: {reason_code}")

    def on_publish(client, userdata, message_id, reason_code, properties):
        del client, userdata, properties
        print(f"MQTT: publish {message_id} acknowledgement: {reason_code}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        del client, userdata, disconnect_flags, properties
        if reason_code != 0:
            print(f"MQTT: broker disconnected with reason: {reason_code}")

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect
    username, password = os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")
    if username and password:
        client.username_pw_set(username, password)
    if os.getenv("MQTT_TLS", "false").lower() == "true":
        client.tls_set()
    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
        info = client.publish(topic, raw, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"could not queue MQTT publish (rc={info.rc}: {mqtt.error_string(info.rc)})"
            )
        try:
            info.wait_for_publish(timeout=15)
        except RuntimeError as exc:
            raise RuntimeError(
                f"MQTT publish {info.mid} failed (rc={info.rc}: {mqtt.error_string(info.rc)}): {exc}"
            ) from exc
        if not info.is_published():
            raise RuntimeError(
                f"MQTT publish {info.mid} was not acknowledged within 15 seconds "
                f"(rc={info.rc}: {mqtt.error_string(info.rc)})"
            )
        print(f"MQTT: published sensor telemetry to {host}:{port}/{topic} (QoS 1)")
    finally:
        client.disconnect()
        client.loop_stop()


def publish_citizen_survey(sample_dir: Path) -> None:
    sample, raw = _read_sample(sample_dir, "sample_citizen_survey.json")
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
        channel.queue_declare(queue=CITIZEN_SURVEY_QUEUE, durable=True)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange="",
            routing_key=CITIZEN_SURVEY_QUEUE,
            body=raw,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=pika.DeliveryMode.Persistent,
                message_id=sample["event_id"],
                type="CITIZEN_SURVEY",
            ),
            mandatory=True,
        )
        print(f"RabbitMQ: published citizen survey to durable queue {CITIZEN_SURVEY_QUEUE}")
    finally:
        connection.close()


def publish_public_health_api(sample_dir: Path, base_url: str) -> None:
    _, raw = _read_sample(sample_dir, "sample_public_health.json")
    request = Request(
        f"{base_url.rstrip('/')}/ingest",
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(
                "HTTP API: accepted public-health event "
                f"{result['event_id']} ({result['source_type']})"
            )
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP API returned {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach ingestion app at {base_url}: {exc.reason}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_demo_dir = Path(__file__).resolve().parents[3] / "demo"
    parser.add_argument(
        "--sample-dir",
        type=Path,
        default=repo_demo_dir,
        help=f"directory containing demo JSON files (default: {repo_demo_dir})",
    )
    parser.add_argument(
        "--base-url",
        default=f"http://localhost:{os.getenv('APP_PORT', '8000')}",
        help="ingestion API base URL (defaults to APP_PORT)",
    )
    args = parser.parse_args()

    publish_sensor_mqtt(args.sample_dir)
    publish_citizen_survey(args.sample_dir)
    publish_public_health_api(args.sample_dir, args.base_url)


if __name__ == "__main__":
    main()
