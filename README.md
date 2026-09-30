# OneAquaHealth

This repository contains the OAH Pydantic models and reusable ingestion components for the hackathon prototype.

## Layout

- `oah-pydantic-models/` contains the OAH logical data models based on the OAH FHIR Implementation Guide.
- `oah-ingestion/` contains health-data and sensor validation, normalization, and RabbitMQ publishing code.
- `connectors/mqtt_sensor.py` subscribes to the sensor MQTT topic and forwards validated events to RabbitMQ.
- The local FastAPI/CSV data-entry adapter and mock uploads remain in the parent hackathon workspace; they are not part of this repository.
- `docker-compose.yml` starts the local RabbitMQ broker used by the ingestion components.

## Install and test

From this repository directory:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s oah-ingestion/tests -v
python oah-pydantic-models/examples/build_examples.py
```

Start RabbitMQ with `docker compose up -d rabbitmq`, then start the sensor listener from this directory with `python connectors/mqtt_sensor.py`. It subscribes to `oneaquahealth/sensors/+/+` at `broker.hivemq.com` by default. Configure `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, and `MQTT_PASSWORD` to use another broker. Accepted sensor events are published persistently to `sensor.telemetry`; the MQTT QoS 1 packet is acknowledged only after RabbitMQ confirms the publish.

The health publisher sends persistent batches to `health.measures`. Both publishers read `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USER`, and `RABBITMQ_PASSWORD`; defaults match the compose file. A consumer that writes queued events to the FHIR server remains a separate next stage.
