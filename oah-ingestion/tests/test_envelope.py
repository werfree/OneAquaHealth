import json
import unittest
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from oah_ingestion.envelope import IngestionEnvelope, envelope_as_message


SAMPLES = Path(__file__).parents[2] / "demo"
ENVELOPE_ADAPTER = TypeAdapter(IngestionEnvelope)


class IngestionEnvelopeTests(unittest.TestCase):
    def test_all_demo_samples_validate_and_preserve_stream_discriminator(self):
        expected = {
            "sample_iot_telemetry.json": "IOT_TELEMETRY",
            "sample_citizen_survey.json": "CITIZEN_SURVEY",
            "sample_public_health.json": "PUBLIC_HEALTH",
        }
        for filename, source_type in expected.items():
            with self.subTest(source_type=source_type):
                raw = json.loads((SAMPLES / filename).read_text(encoding="utf-8"))
                envelope = ENVELOPE_ADAPTER.validate_python(raw)
                self.assertEqual(envelope.source_type, source_type)
                self.assertEqual(envelope.city, "coimbra")

    def test_gateway_generates_event_id_and_received_at(self):
        raw = json.loads((SAMPLES / "sample_citizen_survey.json").read_text(encoding="utf-8"))
        envelope = ENVELOPE_ADAPTER.validate_python(raw)
        message = envelope_as_message(envelope)
        self.assertNotEqual(message["event_id"], raw["event_id"])
        self.assertNotEqual(message["received_at"], raw["received_at"])
        self.assertEqual(message["source_type"], "CITIZEN_SURVEY")

    def test_rejects_unknown_stream_type_and_invalid_risk_score(self):
        raw = json.loads((SAMPLES / "sample_public_health.json").read_text(encoding="utf-8"))
        raw["payload"]["risk_scores"][0]["score"] = 1.5
        with self.assertRaises(ValidationError):
            ENVELOPE_ADAPTER.validate_python(raw)
        raw["source_type"] = "OTHER"
        with self.assertRaises(ValidationError):
            ENVELOPE_ADAPTER.validate_python(raw)


if __name__ == "__main__":
    unittest.main()
