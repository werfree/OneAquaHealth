"""Station views carry observations; model-facing dataset briefings stay compact."""

import unittest
from unittest import mock

from oah_agent import briefing


class BriefingTests(unittest.TestCase):
    def setUp(self):
        # 60 mg/L clears the India screening limit for nitrate (IS 10500:2012, 45 mg/L),
        # so this fixture still exercises the environmental-exceedance branch.
        self.environmental = [{"id": "env-1", "indicator": "nitrate", "value": 60.0, "unit": "mg/L", "when": "2026-09-30T10:00:00+00:00"}]
        self.health = [{"id": "health-1", "indicator": "risk", "value": 0.8, "unit": "{score} (HIGH)", "cohort": "cohort-1", "when": "2026-10-01T10:00:00+00:00"}]
        profile = {"environmental_observations": self.environmental, "health_observations": self.health, "cohorts": ["cohort-1"], "fhir_urls": {}}
        for name, result in (("get_site_profile", profile), ("get_cohort", {"id": "cohort-1"})):
            patch = mock.patch.object(briefing, name, return_value=result)
            patch.start()
            self.addCleanup(patch.stop)

    def test_station_metadata_and_cross_domain_findings(self):
        result = briefing.site_briefing("site-c1-mondego")
        self.assertEqual(result["city"], "coimbra")
        self.assertEqual(result["observed_at"], self.health[0]["when"])
        self.assertTrue(result["co_location"])
        self.assertEqual(result["exceedances"][0]["observation_id"], "env-1")
        self.assertEqual(result["elevated_risks"][0]["interpretation"], "HIGH")

    def test_observations_only_in_station_view(self):
        compact = briefing.site_briefing("site-c1-mondego")
        detailed = briefing.site_briefing("site-c1-mondego", include_observations=True)
        self.assertNotIn("environmental_observations", compact)
        self.assertNotIn("health_observations", compact)
        self.assertEqual(detailed["environmental_observations"], self.environmental)
        self.assertEqual(detailed["health_observations"], self.health)

    def test_dataset_uses_fhir_locations_without_observation_lists(self):
        sites = [
            {"site_id": "site-c1-mondego", "name": "FHIR Mondego", "latitude": 40.2, "longitude": -8.4},
            {"site_id": "unknown-site", "name": "External station", "latitude": 19.0, "longitude": 72.0},
        ]
        with mock.patch.object(briefing, "list_sites", return_value={"sites": sites}), mock.patch.dict("os.environ", {"OAH_BRIEFING_WORKERS": "2"}):
            result = briefing.dataset_briefing("test-tag")
        self.assertEqual(result["site_count"], 2)
        for item, site in zip(result["briefings"], sites):
            for key in ("site_id", "name", "latitude", "longitude"):
                self.assertEqual(item[key], site[key])
            self.assertNotIn("environmental_observations", item)
            self.assertNotIn("health_observations", item)
        self.assertIsNone(result["briefings"][1]["city"])

    def test_missing_observation_times(self):
        self.assertIsNone(briefing._latest([{"id": "untimed"}]))
