"""Paginated searches must collect all pages without touching a server."""

import unittest
from unittest import mock

from oah_ingestion import fhir_client


class SearchTests(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict("os.environ", {"FHIR_BASE_URL": "https://fhir.test", "FHIR_MAX_SEARCH_RESULTS": "5000"})
        env.start()
        self.addCleanup(env.stop)
        self.first = "https://fhir.test/Observation?_count=2"
        self.second = "https://fhir.test/page/2"
        self.third = "https://fhir.test/page/3"
        self.resources = [{"id": str(i)} for i in range(5)]
        self.pages = {
            self.first: self.page(self.resources[:2], self.second),
            self.second: self.page(self.resources[2:4], self.third),
            self.third: self.page(self.resources[4:]),
        }

    @staticmethod
    def page(resources, next_url=None):
        return {
            "entry": [{"resource": resource} for resource in resources] + [{"search": {}}],
            "link": [{"relation": "next", "url": next_url}] if next_url else [],
        }

    def request(self, method, url, **kwargs):
        self.assertEqual(method, "GET")
        return self.pages[url]

    def test_follows_all_three_pages_in_order(self):
        with mock.patch.object(fhir_client, "_request", side_effect=self.request) as request:
            result = fhir_client.search("Observation", {"_count": "2"})
        self.assertEqual(result, self.resources)
        self.assertEqual([call.args[1] for call in request.call_args_list], [self.first, self.second, self.third])

    def test_max_results_stops_mid_page(self):
        with mock.patch.object(fhir_client, "_request", side_effect=self.request) as request:
            result = fhir_client.search("Observation", {"_count": "2"}, max_results=3)
        self.assertEqual(result, self.resources[:3])
        self.assertEqual(request.call_count, 2)

    def test_repeated_next_link_stops(self):
        self.pages[self.first] = self.page(self.resources[:2], self.first)
        with mock.patch.object(fhir_client, "_request", side_effect=self.request) as request:
            result = fhir_client.search("Observation", {"_count": "2"})
        self.assertEqual(result, self.resources[:2])
        self.assertEqual(request.call_count, 1)

    def test_environment_limit_and_timeout_are_used(self):
        with mock.patch.dict("os.environ", {"FHIR_MAX_SEARCH_RESULTS": "1"}), mock.patch.object(
            fhir_client, "_request", side_effect=self.request
        ) as request:
            result = fhir_client.search("Observation", {"_count": "2"}, timeout=17)
        self.assertEqual(result, self.resources[:1])
        request.assert_called_once_with("GET", self.first, timeout=17)
