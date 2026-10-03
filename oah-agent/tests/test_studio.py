"""Tests for the orchestrating studio.

Both cases here are regressions from real failures observed in a live run, not
hypotheticals.
"""

import unittest

from oah_agent import grounding, studio


class ArgumentCleaningTests(unittest.TestCase):
    """A guessed argument should cost a retry at worst, never kill the call."""

    def test_window_days_is_translated_to_days(self):
        # `rank_wards` RETURNS `window_days`, so the model reasonably assumed the
        # show_* tools accept it. They take `days`, and the call died outright.
        self.assertEqual(studio._clean(studio.show_ranking, {"window_days": 7}), {"days": 7})

    def test_station_and_parameter_aliases_are_translated(self):
        cleaned = studio._clean(studio.show_trend, {"station": "yam-ito", "parameter": "bod"})
        self.assertEqual(cleaned, {"site_id": "yam-ito", "indicator": "bod"})

    def test_an_argument_the_tool_cannot_accept_is_dropped_not_raised(self):
        self.assertEqual(studio._clean(studio.show_ranking, {"days": 7, "invented": 1}), {"days": 7})

    def test_accepted_arguments_pass_through_untouched(self):
        self.assertEqual(
            studio._clean(studio.show_matrix, {"days": 14, "caption": "x"}), {"days": 14, "caption": "x"}
        )


class GroundingSourceTests(unittest.TestCase):
    """What the investigation retrieved is broader than what the model was shown."""

    def test_a_charts_data_counts_as_a_source(self):
        # A chart's spec never reaches the model, but it was retrieved and it is
        # on the officer's screen. Excluding it marked every figure read off a
        # chart as unsupported.
        render = {"type": "matrix", "rows": [{"readings": {"bod": {"value": 11.84}}}]}
        self.assertTrue(grounding.check("BOD is 11.84 mg/L.", [render])["grounded"])

    def test_query_arguments_count_as_sources(self):
        # "the past 28 days" is a fact about the investigation, not an invention;
        # 28 was the window the query actually ran with.
        self.assertTrue(grounding.check("Over the past 28 days…", [{"days": 28}])["grounded"])

    def test_a_figure_from_nowhere_is_still_caught(self):
        verdict = grounding.check("Coliform reached 99999 MPN/100mL.", [{"days": 28}, {"value": 21000}])
        self.assertFalse(verdict["grounded"])
        self.assertIn(99999.0, verdict["unsupported_figures"])

    def test_an_answer_with_no_numbers_is_not_reported_as_verified(self):
        verdict = grounding.check("Conditions are concerning.", [{"value": 21000}])
        self.assertEqual(verdict["figures_checked"], 0)
        self.assertIn("not the same as having been verified", grounding.format_verdict(verdict))


if __name__ == "__main__":
    unittest.main()
