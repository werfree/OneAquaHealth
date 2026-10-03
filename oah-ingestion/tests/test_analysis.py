"""Tests for the longitudinal, persistence and offset analyses.

These exist because each makes a claim an officer would escalate on, and a
wrong one is worse than none: a misattributed river stretch sends a sampling
team to the wrong place.
"""

import unittest
from unittest import mock

from oah_ingestion import officer


def reading(site, value, date="2026-10-01", indicator="faecal_coliform"):
    return {"id": f"{site}-{date}", "indicator": indicator, "site_id": site, "when": date + "T09:00:00+00:00",
            "date": date, "value": value, "unit": "MPN/100mL", "cases": None, "population": None,
            "baseline": None, "cohort": None}


class RiverProfileTests(unittest.TestCase):
    def test_stations_come_back_in_downstream_order(self):
        with mock.patch.object(officer, "_water", return_value=[reading("x", 1000.0)]):
            profile = officer.river_profile(river="Yamuna", indicator="faecal_coliform", days=14)
        self.assertEqual([p["site_id"] for p in profile["points"]],
                         ["yam-wazirabad", "yam-ito", "yam-okhla"])
        self.assertEqual([p["flow_km"] for p in profile["points"]], [0, 12, 22])

    def test_the_step_between_stations_names_the_stretch(self):
        # The whole point: not "the river is bad" but "it enters on this reach".
        values = {"yam-wazirabad": 900.0, "yam-ito": 36000.0, "yam-okhla": 34000.0}
        with mock.patch.object(officer, "_water", side_effect=lambda site_id=None, **kw: [reading(site_id, values[site_id])]):
            profile = officer.river_profile(river="Yamuna", indicator="faecal_coliform", days=14)
        worst = profile["largest_increase"]
        self.assertEqual((worst["from"], worst["to"]), ("yam-wazirabad", "yam-ito"))
        self.assertEqual(worst["reach_km"], 12)
        self.assertGreater(worst["ratio"], 30)

    def test_an_unmonitored_river_is_an_error_not_an_empty_chart(self):
        with self.assertRaises(Exception):
            officer.river_profile(river="Kaveri", indicator="faecal_coliform", days=14)


class PersistenceTests(unittest.TestCase):
    def test_counts_days_over_and_the_longest_consecutive_run(self):
        series = [reading("yam-ito", v, f"2026-09-{d:02d}")
                  for d, v in zip(range(1, 7), [100.0, 9000.0, 9000.0, 9000.0, 100.0, 9000.0])]
        with mock.patch.object(officer, "_water", return_value=series):
            result = officer.persistence(days=28, indicator="faecal_coliform")
        station = next(s for s in result["stations"] if s["site_id"] == "yam-ito")
        self.assertEqual(station["days_measured"], 6)
        self.assertEqual(station["days_over"], 4)
        self.assertEqual(station["longest_run"], 3)   # not 4 -- one day dips back inside

    def test_a_station_within_criteria_throughout_reports_zero(self):
        with mock.patch.object(officer, "_water", return_value=[reading("yam-ito", 400.0)]):
            result = officer.persistence(days=28, indicator="faecal_coliform")
        station = next(s for s in result["stations"] if s["site_id"] == "yam-ito")
        self.assertEqual(station["days_over"], 0)
        self.assertEqual(station["pct_over"], 0)


class PeakOffsetTests(unittest.TestCase):
    def test_reports_the_gap_between_the_two_maxima(self):
        water = {"series": [{"date": "2026-09-20", "value": 2.0}, {"date": "2026-09-23", "value": 90.0}],
                 "unit": "MPN/100mL"}
        health = {"series": [{"date": "2026-09-25", "value": 20.0}, {"date": "2026-09-30", "value": 70.0}],
                  "unit": "per 100,000"}
        with mock.patch.object(officer, "trend", side_effect=[water, health]):
            result = officer.peak_offset(site_id="yam-ito", indicator="faecal_coliform", days=28)
        self.assertEqual(result["offset_days"], 7)
        self.assertIn("after the water peak", result["interpretation"])

    def test_a_case_peak_before_the_water_peak_is_called_out(self):
        water = {"series": [{"date": "2026-09-30", "value": 90.0}], "unit": "MPN/100mL"}
        health = {"series": [{"date": "2026-09-20", "value": 70.0}], "unit": "per 100,000"}
        with mock.patch.object(officer, "trend", side_effect=[water, health]):
            result = officer.peak_offset(site_id="yam-ito", days=28)
        self.assertEqual(result["offset_days"], -10)
        self.assertIn("does not fit a waterborne route", result["interpretation"])

    def test_it_refuses_to_call_itself_a_correlation(self):
        water = {"series": [{"date": "2026-09-20", "value": 2.0}], "unit": "x"}
        health = {"series": [{"date": "2026-09-27", "value": 20.0}], "unit": "y"}
        with mock.patch.object(officer, "trend", side_effect=[water, health]):
            result = officer.peak_offset(site_id="yam-ito", days=28)
        self.assertIn("not a correlation", result["caveat"])
        self.assertIn("never as evidence", result["caveat"])


if __name__ == "__main__":
    unittest.main()
