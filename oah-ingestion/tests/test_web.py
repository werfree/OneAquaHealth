"""Read API contracts and cache behavior, with every external call stubbed."""

import copy
import unittest
from unittest import mock

from fastapi import HTTPException

from oah_ingestion import web
from oah_ingestion.sites import lookup


class WebTests(unittest.TestCase):
    def setUp(self):
        web.invalidate_overview()
        self.addCleanup(web.invalidate_overview)
        env = mock.patch.dict("os.environ", {"OAH_DATASET_TAG": "test-tag", "OVERVIEW_CACHE_SECONDS": "60"})
        env.start()
        self.addCleanup(env.stop)
        self.facts = {"site_count": 1, "briefings": [{"site_id": "site-c1-mondego"}]}

    def test_overview_gazetteer_fallback(self):
        with mock.patch("oah_agent.briefing.dataset_briefing", return_value=self.facts):
            result = web.overview()
        site = lookup("site-c1-mondego")
        item = result["briefings"][0]
        self.assertEqual((item["name"], item["city"], item["latitude"], item["longitude"]), (site.name, "coimbra", site.latitude, site.longitude))
        self.assertEqual(result["dataset_tag"], "test-tag")
        self.assertIn("generated_at", result)

    def test_fhir_location_details_win(self):
        self.facts["briefings"][0].update(name="FHIR station", latitude=1.2, longitude=3.4)
        with mock.patch("oah_agent.briefing.dataset_briefing", return_value=self.facts):
            result = web.overview()["briefings"][0]
        self.assertEqual((result["name"], result["latitude"], result["longitude"]), ("FHIR station", 1.2, 3.4))
        self.assertEqual(result["city"], "coimbra")

    def test_overview_cache_refresh_and_invalidation(self):
        with mock.patch("oah_agent.briefing.dataset_briefing", side_effect=lambda **kwargs: copy.deepcopy(self.facts)) as run:
            first = web.overview()
            self.assertIs(first, web.overview())
            self.assertEqual(run.call_count, 1)
            web.overview(refresh=True)
            self.assertEqual(run.call_count, 2)
            web.invalidate_overview()
            web.overview()
            self.assertEqual(run.call_count, 3)

    def test_expired_or_different_dataset_cache_recomputes(self):
        with mock.patch("oah_agent.briefing.dataset_briefing", side_effect=lambda **kwargs: copy.deepcopy(self.facts)) as run:
            web.overview()
            with mock.patch.dict("os.environ", {"OVERVIEW_CACHE_SECONDS": "0"}):
                web.overview()
            with mock.patch.dict("os.environ", {"OAH_DATASET_TAG": "another-tag"}):
                self.assertEqual(web.overview()["dataset_tag"], "another-tag")
            self.assertEqual(run.call_count, 3)

    def test_site_detail_includes_observations_and_fhir_location(self):
        station = {"site_id": "site-c1-mondego", "environmental_reading_count": 1, "health_measure_count": 0, "environmental_observations": [{"id": "obs-1"}], "health_observations": []}
        locations = {"sites": [{"site_id": "site-c1-mondego", "name": "FHIR station", "latitude": 0, "longitude": 0}]}
        with mock.patch("oah_agent.briefing.site_briefing", return_value=station) as run, mock.patch("oah_agent.tools.list_sites", return_value=locations):
            result = web.site_detail("site-c1-mondego")
        run.assert_called_once_with("site-c1-mondego", dataset_tag="test-tag", include_observations=True)
        self.assertEqual(result["environmental_observations"], [{"id": "obs-1"}])
        self.assertEqual((result["name"], result["latitude"], result["longitude"]), ("FHIR station", 0, 0))
        self.assertEqual(result["city"], "coimbra")

    def test_site_detail_without_observations_is_404(self):
        with mock.patch("oah_agent.briefing.site_briefing", return_value={"environmental_reading_count": 0, "health_measure_count": 0}), mock.patch("oah_agent.tools.list_sites") as locations:
            with self.assertRaises(HTTPException) as raised:
                web.site_detail("nowhere")
        self.assertEqual(raised.exception.status_code, 404)
        locations.assert_not_called()

    def test_ask_adds_site_context_and_preserves_original_question(self):
        answer = {"answer": "Recorded findings", "trace": [], "grounding": {}, "model": "stub"}
        with mock.patch("oah_agent.assistant.ask", return_value=answer) as run:
            result = web.ask(web.Question(question="What needs attention?", site_id="site-c1-mondego"))
        self.assertIn("site-c1-mondego", run.call_args.args[0])
        self.assertTrue(run.call_args.args[0].endswith("What needs attention?"))
        self.assertEqual(result["question"], "What needs attention?")

    def test_ask_without_site_preserves_question(self):
        with mock.patch("oah_agent.assistant.ask", return_value={"answer": "", "trace": [], "grounding": {}, "model": "stub"}) as run:
            web.ask(web.Question(question="Dataset summary?"))
        run.assert_called_once_with("Dataset summary?")

    def test_successful_demo_upload_invalidates_overview(self):
        for outcome in ("UPLOADED", "BUILT_NOT_SENT", "UPLOAD_FAILED"):
            with self.subTest(outcome=outcome), mock.patch.object(web, "process", return_value={"fhir": outcome}), mock.patch.object(web, "invalidate_overview") as invalidate:
                web.ingest_demo("iot")
                self.assertEqual(invalidate.call_count, int(outcome == "UPLOADED"))
