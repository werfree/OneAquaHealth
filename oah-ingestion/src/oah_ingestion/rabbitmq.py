"""RabbitMQ transport for OneAquaHealth ingestion events."""

import json
import os


HEALTH_QUEUE = "health.measures"


def publish_health_message(message: dict) -> None:
    """Publish a persistent health batch and require broker confirmation."""
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
        channel.queue_declare(queue=HEALTH_QUEUE, durable=True)
        channel.confirm_delivery()
        confirmed = channel.basic_publish(
            exchange="",
            routing_key=HEALTH_QUEUE,
            body=json.dumps(message, separators=(",", ":")).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=pika.DeliveryMode.Persistent,
                message_id=message["event_id"],
            ),
            mandatory=True,
        )
        if not confirmed:
            raise RuntimeError("RabbitMQ did not confirm the health-data message")
    finally:
        connection.close()
