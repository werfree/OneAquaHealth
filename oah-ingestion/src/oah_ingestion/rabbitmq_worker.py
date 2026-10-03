"""RabbitMQ consumer for citizen science survey input."""

import logging
import os
import threading
import time

from .envelope import CitizenSurveyEnvelope, envelope_as_message
from .rabbitmq import CITIZEN_SURVEY_QUEUE

logger = logging.getLogger("OAH_RabbitMQ_Consumer")


def _parameters(pika):
    return pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "localhost"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
        credentials=pika.PlainCredentials(
            os.getenv("RABBITMQ_USER", "oah"),
            os.getenv("RABBITMQ_PASSWORD", "oah-local-dev"),
        ),
        heartbeat=30,
        blocked_connection_timeout=30,
    )


def consume_citizen_surveys(stop_event: threading.Event, emit_event) -> None:
    """Consume surveys and acknowledge only after the downstream pipeline succeeds."""
    try:
        import pika
    except ImportError as exc:
        logger.error("RabbitMQ support requires pika: %s", exc)
        return

    retry_delay = max(0.1, float(os.getenv("FHIR_RETRY_DELAY_SECONDS", "5")))

    while not stop_event.is_set():
        connection = None
        try:
            connection = pika.BlockingConnection(_parameters(pika))
            channel = connection.channel()
            channel.queue_declare(queue=CITIZEN_SURVEY_QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)

            def handle_message(ch, method, properties, body):
                del properties
                try:
                    envelope = CitizenSurveyEnvelope.model_validate_json(body)
                except Exception:
                    logger.exception("Rejected invalid citizen survey message")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return

                try:
                    result = emit_event(envelope, envelope_as_message(envelope))
                except Exception:
                    logger.exception("Could not process citizen survey; retrying after %.1f seconds", retry_delay)
                    connection.sleep(retry_delay)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    return

                status = result.get("fhir") if isinstance(result, dict) else None
                if status == "UPLOAD_FAILED":
                    logger.error("FHIR upload failed for citizen survey; retrying after %.1f seconds", retry_delay)
                    connection.sleep(retry_delay)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                elif status == "CONVERSION_FAILED":
                    logger.error("FHIR conversion failed for citizen survey; rejecting message")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                else:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(
                queue=CITIZEN_SURVEY_QUEUE,
                on_message_callback=handle_message,
                auto_ack=False,
            )
            logger.info("Consuming citizen surveys from %s", CITIZEN_SURVEY_QUEUE)
            while not stop_event.is_set() and connection.is_open:
                connection.process_data_events(time_limit=1)
        except Exception:
            if not stop_event.is_set():
                logger.exception("Citizen survey RabbitMQ consumer disconnected; retrying in 3 seconds")
                stop_event.wait(3)
        finally:
            if connection is not None and connection.is_open:
                connection.close()
