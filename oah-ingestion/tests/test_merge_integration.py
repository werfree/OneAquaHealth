"""Both deployments must coexist without weakening ingestion or changing legacy facts."""

import json
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from pydantic import TypeAdapter

from oah_ingestion import alerts, fhir_client, officer, pipeline, thresholds, web
from oah_ingestion.envelope import IngestionEnvelope
from oah_ingestion.fhir_adapter import envelope_to_fhir
from oah_ingestion.sites import lookup

DEMO = Path(__file__).resolve().parents[2] / "demo"
ADAPTER = TypeAdapter(IngestionEnvelope)


def sample(name):
    return ADAPTER.validate_json((DEMO / name).read_text())


class DeploymentCompatibilityTests(unittest.TestCase):
    def test_every_gateway_sample_validates_and_maps(self):
        for key, (filename, _, _) in web.SAMPLES.items():
            with self.subTest(sample=key):
                resources = envelope_to_fhir(sample(filename))
                self.assertTrue(any(resource.resourceType == "Observation" for resource in resources))

    def test_both_gazetteers_remain_positioned(self):
        for site_id, city in (("site-c1-mondego", "coimbra"), ("site-ghent-leie-02", "ghent"), ("yam-ito", "delhi")):
            site = lookup(site_id)
            self.assertEqual(site.city, city)
            self.assertIsNotNone(site.latitude)
            self.assertIsNotNone(site.longitude)

    def test_nitrate_and_ph_criteria_remain_deployment_specific(self):
        european = thresholds.evaluate("nitrate", 14.2, "mg/L", city="coimbra")
        self.assertEqual(european["threshold"], 11.3)
        self.assertIsNone(thresholds.evaluate("nitrate", 14.2, "mg/L", city="delhi"))
        self.assertEqual(thresholds.evaluate("nitrate", 50, "mg/L", city="delhi")["threshold"], 45)
        self.assertIsNone(thresholds.evaluate("ph", 8.8, "pH", city="coimbra"))
        self.assertIsNotNone(thresholds.evaluate("ph", 8.8, "pH", city="delhi"))

    def test_original_coimbra_alerts_still_screen_nitrate_and_zinc(self):
        result = alerts.assess(sample("sample_iot_telemetry_coimbra.json"))
        self.assertEqual({e["indicator"] for e in result["exceedances"]}, {"nitrate", "zinc_dissolved"})
        self.assertEqual(result["severity"], "HIGH")

    def test_oxygen_severity_distinguishes_moderate_deficit_and_zero(self):
        for value, expected in ((3.0, "MODERATE"), (2.0, "HIGH"), (0.0, "HIGH")):
            result = thresholds.evaluate("dissolved_oxygen", value, "mg/L", city="delhi")
            self.assertEqual(thresholds.severity_of([result], city="delhi"), expected)

    def test_disease_counts_and_population_survive_fhir_mapping(self):
        envelope = sample("sample_public_health.json")
        resources = envelope_to_fhir(envelope)
        for line in envelope.payload.disease_surveillance:
            observation = next(r for r in resources if r.resourceType == "Observation" and r.code.coding[0].code == line.condition)
            components = {c.code.coding[0].code: c.valueQuantity.value for c in observation.component}
            self.assertEqual(observation.valueQuantity.value, line.rate_per_100k)
            self.assertEqual(components["cases"], line.cases)
            self.assertEqual(components["populationAtRisk"], line.population_at_risk)
            self.assertEqual(components["baseline"], line.baseline_rate_per_100k)


class QueryCompatibilityTests(unittest.TestCase):
    def test_date_bounds_are_repeated_and_parameters_remain_tagged(self):
        from oah_agent import tools

        with mock.patch.object(tools, "search", return_value=[]) as search:
            result = tools.search_observations(since="2026-09-01", until="2026-09-30", dataset_tag="private-tag")
        params = parse_qs(urlparse(result["fhir_url"]).query)
        self.assertEqual(params["date"], ["ge2026-09-01", "le2026-09-30"])
        self.assertIn("private-tag", params["_tag"][0])
        self.assertEqual(search.call_args.args[1]["_sort"], "-date")

    def test_officer_queries_restore_chronological_health_order(self):
        rows = [
            {"id": "new", "effectiveDateTime": "2026-10-01T00:00:00Z", "valueQuantity": {"value": 70}},
            {"id": "old", "effectiveDateTime": "2026-09-01T00:00:00Z", "valueQuantity": {"value": 20}},
        ]
        with mock.patch.object(officer, "search", return_value=rows) as search:
            result = officer.trend("yam-ito", "acute_diarrhoeal_disease", days=28)
        self.assertEqual(result["latest"], 70)
        self.assertEqual([point["value"] for point in result["series"]], [20, 70])
        self.assertEqual(search.call_args.args[1]["_sort"], "-date")

    def test_persistence_counts_sampling_days_not_individual_readings(self):
        rows = [
            {"site_id": "yam-ito", "date": "2026-10-01", "when": "2026-10-01T09:00:00Z", "value": 9000, "unit": "MPN/100mL"},
            {"site_id": "yam-ito", "date": "2026-10-01", "when": "2026-10-01T10:00:00Z", "value": 100, "unit": "MPN/100mL"},
            {"site_id": "yam-ito", "date": "2026-10-02", "when": "2026-10-02T09:00:00Z", "value": 9000, "unit": "MPN/100mL"},
        ]
        with mock.patch.object(officer, "_water", return_value=rows):
            result = officer.persistence(days=28, indicator="faecal_coliform")
        self.assertEqual(result["stations"][0]["days_measured"], 2)
        self.assertEqual(result["stations"][0]["days_over"], 1)


class UploadReliabilityTests(unittest.TestCase):
    def test_partial_upload_remains_failed(self):
        envelope = sample("sample_iot_telemetry_coimbra.json")
        with mock.patch.object(pipeline, "upload_enabled", return_value=True), mock.patch.object(pipeline, "upload_bundle", return_value=(1, 2)), mock.patch.object(pipeline, "raise_for"):
            result = pipeline.process(envelope)
        self.assertEqual(result["fhir"], "UPLOAD_FAILED")
        self.assertGreater(result["failed"], 0)

    def test_missing_transaction_entries_remain_failed(self):
        with mock.patch.object(fhir_client, "_request", return_value={"entry": [{"response": {"status": "200 OK"}}]}):
            self.assertEqual(fhir_client.upload_bundle({"entry": [{}, {}]}), (1, 1))

    def test_timeout_is_retried_with_backoff(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{}'
        response.headers = {}
        with mock.patch.object(fhir_client, "RETRIES", 2), mock.patch.object(fhir_client, "urlopen", side_effect=[TimeoutError("temporary"), response]) as request, mock.patch.object(fhir_client.time, "sleep") as sleep:
            self.assertEqual(fhir_client._request("GET", "https://fhir.test/metadata"), {})
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1)
