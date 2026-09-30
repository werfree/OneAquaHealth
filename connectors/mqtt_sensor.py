"""Subscribe to sensor telemetry and forward validated events to RabbitMQ."""

import logging
import os
import ssl

import paho.mqtt.client as mqtt

from oah_ingestion.sensor import SensorIngestionService, publish_sensor_event


logger = logging.getLogger("OAH_MQTT_Connector")
ingestion = SensorIngestionService()


def on_connect(client, userdata, flags, reason_code, properties):
    del userdata, flags, properties
    if reason_code == 0:
        topic_filter = os.getenv("MQTT_TOPIC", "oneaquahealth/sensors/+/+")
        client.subscribe(topic_filter, qos=1)
        logger.info("Connected; subscribed to %s", topic_filter)
    else:
        logger.error("MQTT connection failed: %s", reason_code)


def on_message(client, userdata, message):
    del client, userdata
    try:
        result = ingestion.process_packet(message.topic, message.payload.decode("utf-8"))
        if result["status"] != "ACCEPTED":
            logger.warning("Rejected MQTT packet on %s: %s", message.topic, result["reason"])
            if message.qos > 0:
                client.ack(message.mid, message.qos)
            return
        event = result["event"]
        publish_sensor_event(event)
        if message.qos > 0:
            client.ack(message.mid, message.qos)
        logger.info("Queued sensor event %s (%d measurements)", event["event_id"], len(event["measurements"]))
    except Exception:
        logger.exception("Could not process/publish MQTT packet on %s", message.topic)


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(message)s")
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=os.getenv("MQTT_CLIENT_ID", "OAH_Sensor_Ingestion_Worker"),
        protocol=mqtt.MQTTv5,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.manual_ack_set(True)
    username, password = os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")
    if username and password:
        client.username_pw_set(username, password)
    if os.getenv("MQTT_TLS", "false").lower() == "true":
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    host = os.getenv("MQTT_HOST", "broker.hivemq.com")
    port = int(os.getenv("MQTT_PORT", "1883"))
    logger.info("Connecting to MQTT broker %s:%d", host, port)
    client.connect(host, port, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Stopping MQTT listener")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
