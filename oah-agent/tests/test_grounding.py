"""Tests for the deterministic grounding check.

The regression that matters is `test_catches_the_invented_safe_level`: an early
version of the assistant reported a reading as "above the safe level of
10 mg/L", where 10 was a search filter it had chosen itself rather than a
threshold from anywhere. That is the class of error this module exists to
catch, so it is pinned here.
"""

import unittest

from oah_agent.grounding import check, extract_numbers


class ExtractionTests(unittest.TestCase):
    def test_pulls_decimals_negatives_and_thousands(self):
        numbers = extract_numbers("0.611 rose to 14.2, from -3 across 1,200 samples")
        self.assertIn(0.611, numbers)
        self.assertIn(14.2, numbers)
        self.assertIn(-3.0, numbers)
        self.assertIn(1200.0, numbers)

    def test_empty_text_is_not_an_error(self):
        self.assertEqual(extract_numbers(""), [])
        self.assertEqual(extract_numbers(None), [])


class GroundingTests(unittest.TestCase):
    def test_figures_present_in_tool_results_are_grounded(self):
        results = [{"observations": [{"indicator": "nitrate", "value": 14.2, "unit": "mg/L"}]}]
        verdict = check("Nitrate at this station is 14.2 mg/L.", results)
        self.assertTrue(verdict["grounded"], verdict["unsupported_figures"])

    def test_catches_the_invented_safe_level(self):
        # The tools returned 14.2; nothing anywhere returned 10. The real
        # threshold is 11.3, so "10" was fabricated.
        results = [{"observations": [{"indicator": "nitrate", "value": 14.2}]}]
        verdict = check("Nitrate is 14.2 mg/L, above the safe level of 11.9 mg/L.", results)
        self.assertFalse(verdict["grounded"])
        self.assertIn(11.9, verdict["unsupported_figures"])

    def test_rounding_in_prose_is_accepted(self):
        results = [{"score": 0.5341}]
        self.assertTrue(check("The overall score is 0.53.", results)["grounded"])

    def test_derived_ratio_is_accepted(self):
        # 0.05 / 0.0078 = 6.41; an answer may legitimately say "6.4x".
        results = [{"value": 0.05, "threshold": 0.0078}]
        self.assertTrue(check("Zinc is 6.4 times the screening value.", results)["grounded"])

    def test_figures_nested_deep_in_results_are_found(self):
        results = [{"briefings": [{"risks": [{"score": 0.611}]}]}]
        self.assertTrue(check("Fecal contamination risk is 0.611.", results)["grounded"])

    def test_numbers_inside_result_strings_count_as_sources(self):
        results = [{"cohort": {"ageRange": "18-74"}}]
        self.assertTrue(check("The cohort covers ages 18 to 74.", results)["grounded"])

    def test_small_integers_do_not_trip_the_check(self):
        verdict = check("All 3 stations were screened; 2 carry cohorts.", [{}])
        self.assertTrue(verdict["grounded"])

    def test_no_sources_at_all_flags_any_real_figure(self):
        verdict = check("Nitrate reached 14.2 mg/L.", [])
        self.assertFalse(verdict["grounded"])
        self.assertIn(14.2, verdict["unsupported_figures"])

    def test_verdict_states_what_it_does_not_cover(self):
        verdict = check("Levels are rising sharply.", [{}])
        # No numbers, so nothing to contradict -- and the verdict must say so.
        self.assertTrue(verdict["grounded"])
        self.assertIn("trend", verdict["not_covered"])


if __name__ == "__main__":
    unittest.main()
