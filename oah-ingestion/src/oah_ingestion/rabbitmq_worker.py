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
    """Consume survey envelopes, normalize and emit them, then acknowledge."""
    try:
        import pika
    except ImportError as exc:
        logger.error("RabbitMQ support requires pika: %s", exc)
        return

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
                    emit_event(envelope_as_message(envelope))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception:
                    logger.exception("Rejected invalid citizen survey message")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

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
