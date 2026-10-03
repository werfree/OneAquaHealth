"""Tests for ingest-time threshold alerting.

Detection has no model in it, so it is fully testable offline -- which is the
point of keeping it in Python. The contract that matters operationally is the
last class: alerting must never be able to break ingestion.
"""

import json
import unittest
from pathlib import Path

from pydantic import TypeAdapter

from oah_ingestion import alerts
from oah_ingestion.envelope import IngestionEnvelope
from oah_ingestion.thresholds import evaluate

SAMPLES = Path(__file__).parents[2] / "demo"
ADAPTER = TypeAdapter(IngestionEnvelope)


def load(name: str):
    return ADAPTER.validate_python(json.loads((SAMPLES / name).read_text(encoding="utf-8")))


class ThresholdTests(unittest.TestCase):
    def test_value_above_limit_is_an_exceedance_with_its_basis(self):
        result = evaluate("faecal_coliform", 21000.0, "MPN/100mL")
        self.assertEqual(result["exceedance_factor"], 8.4)
        self.assertIn("CPCB", result["basis"])

    def test_value_within_limit_is_not_an_exceedance(self):
        self.assertIsNone(evaluate("faecal_coliform", 410.0, "MPN/100mL"))

    def test_ph_is_a_band_not_a_ceiling(self):
        self.assertIsNone(evaluate("ph", 7.4, "pH"))
        self.assertIsNotNone(evaluate("ph", 5.1, "pH"))   # too acidic
        self.assertIsNotNone(evaluate("ph", 9.6, "pH"))   # too alkaline

    def test_dissolved_oxygen_fails_by_being_too_low(self):
        # The only indicator where a SMALL number is the problem.
        self.assertIsNone(evaluate("dissolved_oxygen", 6.8, "mg/L"))
        deficit = evaluate("dissolved_oxygen", 1.0, "mg/L")
        self.assertEqual(deficit["direction"], "deficit")
        self.assertEqual(deficit["exceedance_factor"], 5.0)

    def test_unscreened_indicator_is_not_an_error(self):
        self.assertIsNone(evaluate("riparianVegetation", None))
        self.assertIsNone(evaluate("turbidity", 999.0, "NTU"))


class AssessmentTests(unittest.TestCase):
    def test_iot_exceedance_raises_a_high_alert(self):
        alert = alerts.assess(load("sample_iot_telemetry.json"))
        self.assertEqual(alert["severity"], "HIGH")  # coliform far past criterion
        self.assertEqual(alert["site_id"], "yam-ito")
        self.assertIn("faecal_coliform", {e["indicator"] for e in alert["exceedances"]})

    def test_citizen_survey_raises_nothing_because_answers_are_coded(self):
        self.assertIsNone(alerts.assess(load("sample_citizen_survey.json")))

    def test_public_health_alert_screens_its_chemical_summary(self):
        alert = alerts.assess(load("sample_public_health.json"))
        self.assertEqual(alert["severity"], "HIGH")
        self.assertTrue(alert["exceedances"], "expected the coliform chemical summary to screen")

    def test_co_located_sample_reports_both_domains_in_one_alert(self):
        alert = alerts.assess(load("sample_public_health_kanpur.json"))
        self.assertTrue(alert["exceedances"], "expected the chromium chemical summary to screen")

    def test_every_alert_states_its_limits(self):
        alert = alerts.assess(load("sample_iot_telemetry.json"))
        self.assertIn("not regulatory limits", alert["caveat"])
        self.assertIn("causation", alert["caveat"])

    def test_low_readings_produce_no_alert_at_all(self):
        envelope = ADAPTER.validate_python(
            {
                "source_type": "IOT_TELEMETRY",
                "city": "varanasi",
                "site_id": "gan-assi",
                "timestamp": "2026-09-30T10:00:00Z",
                "payload": {
                    "device_id": "d1",
                    "measurements": [{"parameter": "ph", "unit": "pH", "value": 7.1}],
                },
            }
        )
        self.assertIsNone(alerts.assess(envelope))


class ResilienceTests(unittest.TestCase):
    """Alerting must never be able to break ingestion."""

    def test_a_failing_subscriber_does_not_propagate(self):
        def explode(alert):
            raise RuntimeError("pager is down")

        alerts._handlers.append(explode)
        try:
            with self.assertLogs("OAH_Alerts", level="ERROR"):
                result = alerts.raise_for(load("sample_iot_telemetry.json"))
            self.assertIsNotNone(result, "the alert should still be returned")
        finally:
            alerts._handlers.remove(explode)

    def test_an_unusable_envelope_returns_none_instead_of_raising(self):
        self.assertIsNone(alerts.raise_for(object()))

    def test_subscribers_receive_the_alert(self):
        received = []
        alerts.subscribe(received.append)
        try:
            alerts.raise_for(load("sample_iot_telemetry.json"))
            self.assertEqual(received[0]["site_id"], "yam-ito")
        finally:
            alerts._handlers.remove(received.append) if received.append in alerts._handlers else None
            alerts._handlers.clear()


if __name__ == "__main__":
    unittest.main()
