import unittest
from datetime import date

from oah_ingestion.health import (
    HealthMeasureBatch,
    HealthMeasureInput,
    build_health_message,
    to_oah_health_measure,
)


def sample_record():
    return HealthMeasureInput(
        city="Coimbra",
        site_id="health-coimbra-district",
        site_name="Coimbra District",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        indicator_code="diabetes",
        indicator_display="% of people with diabetes",
        value=8.4,
        unit="%",
        cohort_id="coimbra-all-adults",
        cohort_display="All adults in Coimbra district",
        source_dataset="mock-test",
    )


class HealthCoreTests(unittest.TestCase):
    def test_row_maps_to_oah_health_measure(self):
        measure = to_oah_health_measure(sample_record()).model_dump(mode="json", exclude_none=True)
        self.assertEqual(measure["site"]["identifier"][0]["value"], "health-coimbra-district")
        self.assertEqual(measure["type"]["coding"][0]["code"], "diabetes")
        self.assertEqual(measure["result"]["value"], 8.4)
        self.assertEqual(measure["cohort"]["reference"], "Group/coimbra-all-adults")

    def test_message_is_a_batch_of_oah_models(self):
        message = build_health_message(HealthMeasureBatch(records=[sample_record()]))
        self.assertEqual(message["record_count"], 1)
        self.assertEqual(message["records"][0]["city"], "coimbra")
        self.assertIn("oah_health_measure", message["records"][0])

    def test_rejects_reversed_reporting_period(self):
        record = sample_record().model_dump()
        record["period_start"] = date(2025, 1, 1)
        with self.assertRaises(ValueError):
            HealthMeasureInput.model_validate(record)


if __name__ == "__main__":
    unittest.main()
