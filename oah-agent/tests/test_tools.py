"""Tests for the typed FHIR tools, against a fake transport.

These must not hit the network: a test suite that depends on a public sandbox
fails for reasons that have nothing to do with the code. `oah_ingestion.fhir_client.search`
is replaced with a stub returning canned FHIR resources, which also lets the
awkward shapes be pinned -- a value hiding in `component` rather than
`valueQuantity`, a coded citizen-survey answer, a cohort reference in `focus`.
"""

import unittest
from unittest import mock

from oah_agent import tools


def observation(**kwargs) -> dict:
    base = {
        "resourceType": "Observation",
        "id": "obs-1",
        "code": {"coding": [{"code": "nitrate"}]},
        "subject": {"reference": "Location/site-c1-mondego"},
        "effectiveDateTime": "2026-09-30T10:00:00+00:00",
    }
    base.update(kwargs)
    return base


class SummarizeTests(unittest.TestCase):
    def test_reads_a_plain_value_quantity(self):
        summary = tools._summarize(observation(valueQuantity={"value": 14.2, "unit": "mg/L"}))
        self.assertEqual(summary["value"], 14.2)
        self.assertEqual(summary["unit"], "mg/L")
        self.assertEqual(summary["site"], "site-c1-mondego")

    def test_reads_the_value_out_of_a_component_observation(self):
        # observation-with-component-oah holds the reading in `component`,
        # which no plain valueQuantity lookup would find.
        summary = tools._summarize(
            observation(
                component=[
                    {"code": {"coding": [{"code": "value"}]}, "valueQuantity": {"value": 14.2, "unit": "mg/L"}},
                    {"code": {"coding": [{"code": "maximum"}]}, "valueQuantity": {"value": 16.5, "unit": "mg/L"}},
                ]
            )
        )
        self.assertEqual(summary["value"], 14.2)
        self.assertEqual(summary["unit"], "mg/L")
        self.assertEqual([s["stat"] for s in summary["statistics"]], ["value", "maximum"])

    def test_reads_a_coded_citizen_survey_answer(self):
        summary = tools._summarize(
            observation(
                code={"coding": [{"code": "waterAspect"}]},
                valueCodeableConcept={"coding": [{"code": "foamy"}]},
            )
        )
        self.assertEqual(summary["coded_value"], "foamy")
        self.assertNotIn("value", summary)

    def test_carries_the_cohort_from_focus(self):
        summary = tools._summarize(
            observation(valueQuantity={"value": 0.611}, focus=[{"reference": "Group/group-mondego-riverside-residents"}])
        )
        self.assertEqual(summary["cohort"], "group-mondego-riverside-residents")


class SearchObservationTests(unittest.TestCase):
    def test_rejects_an_unknown_profile_kind_rather_than_querying(self):
        result = tools.search_observations(kind="not-a-profile")
        self.assertIn("error", result)
        self.assertNotIn("observations", result)

    def test_scopes_every_query_to_the_dataset_tag(self):
        with mock.patch.object(tools, "search", return_value=[]) as fake:
            tools.search_observations(kind="health")
        params = fake.call_args[0][1]
        self.assertIn("_tag", params)
        self.assertIn("oah-demo", params["_tag"])
        self.assertIn("observation-health-measure-oah", params["_profile"])

    def test_site_filter_becomes_a_subject_reference(self):
        with mock.patch.object(tools, "search", return_value=[]) as fake:
            tools.search_observations(kind="environmental_simple", site_id="site-c1-mondego")
        self.assertEqual(fake.call_args[0][1]["subject"], "Location/site-c1-mondego")

    def test_min_value_filters_component_observations_too(self):
        # The FHIR value-quantity search parameter cannot reach a number held in
        # `component`, so the filter is applied client-side; this pins that.
        readings = [
            observation(id="low", component=[{"code": {"coding": [{"code": "value"}]}, "valueQuantity": {"value": 2.0}}]),
            observation(id="high", component=[{"code": {"coding": [{"code": "value"}]}, "valueQuantity": {"value": 14.2}}]),
        ]
        with mock.patch.object(tools, "search", return_value=readings):
            result = tools.search_observations(kind="environmental_component", min_value=10)
        self.assertEqual([o["id"] for o in result["observations"]], ["high"])

    def test_every_result_carries_an_auditable_fhir_url(self):
        with mock.patch.object(tools, "search", return_value=[]):
            result = tools.search_observations(kind="health", indicator="pathogen_risk")
        self.assertIn("code=pathogen_risk", result["fhir_url"])

    def test_a_server_error_is_returned_as_data_not_raised(self):
        from oah_ingestion.fhir_client import FhirError

        with mock.patch.object(tools, "search", side_effect=FhirError("server down")):
            result = tools.search_observations(kind="health")
        self.assertIn("error", result)
        self.assertIn("fhir_url", result)


class ThresholdToolTests(unittest.TestCase):
    def test_exposes_real_sourced_thresholds_with_their_basis(self):
        reference = tools.get_thresholds()["thresholds"]
        self.assertIn("nitrate", reference)
        self.assertIn("11.3", reference["nitrate"]["rule"])
        self.assertIn("Drinking Water Directive", reference["nitrate"]["basis"])

    def test_states_that_these_are_not_regulatory_limits(self):
        self.assertIn("not regulatory limits", tools.get_thresholds()["note"])

    def test_agrees_with_the_ingest_time_alerting_table(self):
        # Alerting and the assistant must never disagree about what is elevated.
        from oah_ingestion.thresholds import THRESHOLDS

        self.assertEqual(set(tools.get_thresholds()["thresholds"]), set(THRESHOLDS))


class CohortToolTests(unittest.TestCase):
    def test_flattens_a_group_age_range_to_something_readable(self):
        group = {
            "id": "group-mondego-riverside-residents",
            "name": "riverside residents",
            "characteristic": [
                {
                    "code": {"coding": [{"code": "ageRange"}]},
                    "valueRange": {"low": {"value": 18}, "high": {"value": 74}},
                },
                {"code": {"coding": [{"code": "sex"}]}, "valueCodeableConcept": {"text": "all"}},
            ],
        }
        with mock.patch.object(tools, "search", return_value=[group]):
            result = tools.get_cohort("group-mondego-riverside-residents")
        self.assertEqual(result["characteristics"]["ageRange"], "18-74")
        self.assertEqual(result["characteristics"]["sex"], "all")

    def test_missing_cohort_reports_clearly_rather_than_returning_empty(self):
        with mock.patch.object(tools, "search", return_value=[]):
            result = tools.get_cohort("group-does-not-exist")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
