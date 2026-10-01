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
        result = evaluate("zinc_dissolved", 0.05, "mg/L")
        self.assertEqual(result["exceedance_factor"], 6.41)
        self.assertIn("WFD", result["basis"])

    def test_value_within_limit_is_not_an_exceedance(self):
        self.assertIsNone(evaluate("nitrate", 1.9, "mg/L"))

    def test_ph_is_a_band_not_a_ceiling(self):
        self.assertIsNone(evaluate("ph", 7.4, "pH"))
        self.assertIsNotNone(evaluate("ph", 5.1, "pH"))   # too acidic
        self.assertIsNotNone(evaluate("ph", 9.6, "pH"))   # too alkaline

    def test_unscreened_indicator_is_not_an_error(self):
        self.assertIsNone(evaluate("riparianVegetation", None))
        self.assertIsNone(evaluate("lead_dissolved", 999.0, "mg/L"))


class AssessmentTests(unittest.TestCase):
    def test_iot_exceedance_raises_a_high_alert(self):
        alert = alerts.assess(load("sample_iot_telemetry.json"))
        self.assertEqual(alert["severity"], "HIGH")  # zinc at 6.41x
        self.assertEqual(alert["site_id"], "site-c1-mondego")
        self.assertEqual({e["indicator"] for e in alert["exceedances"]}, {"nitrate", "zinc_dissolved"})

    def test_citizen_survey_raises_nothing_because_answers_are_coded(self):
        self.assertIsNone(alerts.assess(load("sample_citizen_survey.json")))

    def test_public_health_alert_carries_the_agency_interpretation(self):
        alert = alerts.assess(load("sample_public_health.json"))
        self.assertEqual(alert["severity"], "HIGH")
        self.assertIn("fecal_contamination_risk", {r["indicator"] for r in alert["elevated_risks"]})

    def test_co_located_sample_reports_both_domains_in_one_alert(self):
        alert = alerts.assess(load("sample_public_health_mondego.json"))
        self.assertTrue(alert["exceedances"], "expected the nitrate chemical summary to screen")
        self.assertTrue(alert["elevated_risks"], "expected elevated cohort risk")

    def test_every_alert_states_its_limits(self):
        alert = alerts.assess(load("sample_iot_telemetry.json"))
        self.assertIn("not regulatory limits", alert["caveat"])
        self.assertIn("causation", alert["caveat"])

    def test_low_readings_produce_no_alert_at_all(self):
        envelope = ADAPTER.validate_python(
            {
                "source_type": "IOT_TELEMETRY",
                "city": "oslo",
                "site_id": "site-o1-akerselva",
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
            self.assertEqual(received[0]["site_id"], "site-c1-mondego")
        finally:
            alerts._handlers.remove(received.append) if received.append in alerts._handlers else None
            alerts._handlers.clear()


if __name__ == "__main__":
    unittest.main()
