import json
import unittest
from pathlib import Path

from oah_ingestion.sensor import SensorIngestionService

SAMPLE_DATA = Path(__file__).parent


def packet(**overrides):
    value = {
        "device_id": "sensor-001",
        "city": "Delhi",
        "site_id": "yam-ito",
        "timestamp": "2026-09-26T12:00:00Z",
        "measurements": [{"parameter": "ph", "unit": "pH", "value": 7.2}],
    }
    value.update(overrides)
    return json.dumps(value)


class SensorIngestionTests(unittest.TestCase):
    def setUp(self):
        self.service = SensorIngestionService()
        self.topic = "oneaquahealth/sensors/delhi/yam-ito"

    def test_valid_packet_builds_normalized_event(self):
        sample = (SAMPLE_DATA / "sample_sensor_delhi.json").read_text(encoding="utf-8")
        result = self.service.process_packet(self.topic, sample)
        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["event"]["city"], "delhi")
        self.assertEqual(len(result["event"]["measurements"]), 3)
        self.assertEqual(result["event"]["measurements"][0]["value"], 7.2)

    def test_filters_out_of_range_measurements_when_other_values_are_valid(self):
        result = self.service.process_packet(
            self.topic,
            packet(
                measurements=[
                    {"parameter": "ph", "unit": "pH", "value": 7.2},
                    {"parameter": "faecal_coliform", "unit": "MPN/100mL", "value": -1},
                ]
            ),
        )
        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual([m["parameter"] for m in result["event"]["measurements"]], ["ph"])

    def test_rejects_mismatched_topic_and_payload(self):
        result = self.service.process_packet("oneaquahealth/sensors/mumbai/yam-ito", packet())
        self.assertEqual(result["status"], "REJECTED")

    def test_rejects_invalid_ph(self):
        result = self.service.process_packet(
            self.topic,
            packet(measurements=[{"parameter": "ph", "unit": "pH", "value": 17}]),
        )
        self.assertEqual(result["status"], "REJECTED")

    def test_rejects_timestamp_without_timezone(self):
        result = self.service.process_packet(self.topic, packet(timestamp="2026-09-26T12:00:00"))
        self.assertEqual(result["status"], "REJECTED")

    def test_rejects_non_finite_measurement(self):
        result = self.service.process_packet(
            self.topic,
            packet(measurements=[{"parameter": "temperature", "unit": "Cel", "value": float("nan")}]),
        )
        self.assertEqual(result["status"], "REJECTED")

    def test_rejects_wrong_topic_shape(self):
        result = self.service.process_packet("oneaquahealth/sensors/delhi", packet())
        self.assertEqual(result["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
