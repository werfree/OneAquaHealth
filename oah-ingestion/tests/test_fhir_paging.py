"""Regression: a server page cap must not silently truncate a result set.

HAPI returns at most 500 entries regardless of `_count`. The reader took the
first page and stopped, so with an ascending date sort the rows dropped were the
most recent ones -- "the latest reading" came back eleven days stale and every
severity derived from it was wrong. In a tool whose question is "has anything
changed", that is the worst available failure.
"""

import unittest
from unittest import mock

from oah_ingestion import fhir_client, officer


def page(ids, next_url=None):
    bundle = {"resourceType": "Bundle",
              "entry": [{"resource": {"resourceType": "Observation", "id": i}} for i in ids]}
    if next_url:
        bundle["link"] = [{"relation": "next", "url": next_url}]
    return bundle


class PaginationTests(unittest.TestCase):
    def test_follows_next_links_until_exhausted(self):
        pages = [page(["a", "b"], "http://x/2"), page(["c", "d"], "http://x/3"), page(["e"])]
        with mock.patch.object(fhir_client, "_request", side_effect=pages) as req:
            got = fhir_client.search("Observation", {"_count": "2"})
        self.assertEqual([r["id"] for r in got], ["a", "b", "c", "d", "e"])
        self.assertEqual(req.call_count, 3)

    def test_a_single_page_without_a_next_link_stops(self):
        with mock.patch.object(fhir_client, "_request", return_value=page(["a"])) as req:
            got = fhir_client.search("Observation", {})
        self.assertEqual(len(got), 1)
        self.assertEqual(req.call_count, 1)

    def test_page_following_is_bounded_and_warns(self):
        pages = [page([str(i)], f"http://x/next/{i + 1}") for i in range(3)]
        with mock.patch.object(fhir_client, "MAX_PAGES", 3), mock.patch.object(fhir_client, "_request", side_effect=pages):
            with self.assertLogs("OAH_FHIR_Client", level="WARNING") as logs:
                got = fhir_client.search("Observation", {})
        self.assertEqual(len(got), 3)
        self.assertTrue(any("incomplete" in m for m in logs.output))

    def test_paginate_false_reads_one_page(self):
        with mock.patch.object(fhir_client, "_request", return_value=page(["a"], "http://x/2")) as req:
            fhir_client.search("Observation", {}, paginate=False)
        self.assertEqual(req.call_count, 1)


class SortOrderTests(unittest.TestCase):
    def test_observation_queries_sort_newest_first(self):
        # Second line of defence: if anything truncates despite pagination, the
        # rows lost must be the oldest, never the newest.
        with mock.patch.object(officer, "search", return_value=[]) as fake:
            officer._fetch(officer.WATER_PROFILE, since="2026-09-01")
        self.assertEqual(fake.call_args[0][1]["_sort"], "-date")


if __name__ == "__main__":
    unittest.main()
