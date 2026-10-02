"""Regression tests for the OAH -> FHIR mappers.

The import test below is deliberately the first one: `oah_models.fhir` shipped
unimportable (its mappers imported `..health_indicators`/`..indicators`, which
never existed -- the modules are singular), and nothing caught it because
nothing imported the subpackage. This file is that missing guard.
"""

import unittest

from oah_models import SampleOah
from oah_models.common import CodeableConcept, Coding, Gps, Identifier, Period, Quantity, Reference
from oah_models.health_measure import HealthMeasureOah, HealthMeasureSite
from oah_models.sample import SampleSite
from oah_models.simple_indicator import SimpleIndicatorOah
from oah_models.structured_indicator import StructuredIndicatorComponent, StructuredIndicatorOah


def a_sample() -> SampleOah:
    return SampleOah(
        site=SampleSite(
            identifier=[Identifier(system="https://oneaquahealth.eu/location-id", value="coimbra c1")],
            name=["Mondego site 1"],
            gps=Gps(longitude=-8.4377, latitude=40.2194),
        ),
        dateOfSampling="2026-09-30T10:00:00+00:00",
        performer=[Reference(reference="Organization/Org-UC", display="Univ. Coimbra")],
    )


class FhirSubpackageImportTests(unittest.TestCase):
    def test_subpackage_imports_and_exports_all_seven_mappers(self):
        import oah_models.fhir as fhir

        for name in (
            "sample_to_fhir",
            "simple_indicator_to_fhir",
            "structured_indicator_to_fhir",
            "health_measure_to_fhir",
            "health_indicators_to_fhir",
            "indicators_to_fhir",
            "dataset_to_fhir",
        ):
            self.assertTrue(callable(getattr(fhir, name)), f"{name} missing from oah_models.fhir")


class SampleMapperTests(unittest.TestCase):
    def test_location_and_specimen_carry_oah_profiles_and_position(self):
        from oah_models.fhir import sample_to_fhir

        location, specimen = sample_to_fhir(a_sample())
        self.assertEqual(location.meta.profile, ["http://hl7.eu/fhir/ig/oah/StructureDefinition/location-oah"])
        self.assertEqual(specimen.meta.profile, ["http://hl7.eu/fhir/ig/oah/StructureDefinition/specimen-oah"])
        self.assertEqual(location.position.latitude, 40.2194)
        self.assertEqual(specimen.subject.reference, f"Location/{location.id}")

    def test_ids_are_fhir_safe_and_deterministic(self):
        from oah_models.fhir import sample_to_fhir

        location, _ = sample_to_fhir(a_sample())
        # FHIR id is [A-Za-z0-9-.]{1,64}; the source identifier had a space.
        self.assertRegex(location.id, r"^[A-Za-z0-9.\-]{1,64}$")
        again, _ = sample_to_fhir(a_sample())
        self.assertEqual(location.id, again.id, "ids must be deterministic so resources dedupe")


class IndicatorMapperTests(unittest.TestCase):
    def test_simple_indicator_becomes_observation_with_value_quantity(self):
        from oah_models.fhir import simple_indicator_to_fhir

        sample = a_sample()
        obs, location, specimen = simple_indicator_to_fhir(
            SimpleIndicatorOah(
                sampleDetails=sample,
                type=CodeableConcept(coding=[Coding(code="ph", display="pH")]),
                date=["2026-09-30T10:00:00+00:00"],
                performer=sample.performer,
                result=Quantity(value=7.4, unit="pH"),
            )
        )
        self.assertIn("observation-indicators-oah", obs.meta.profile[0])
        self.assertEqual(obs.valueQuantity.value, 7.4)
        self.assertEqual(obs.subject.reference, f"Location/{location.id}")
        self.assertEqual(obs.specimen.reference, f"Specimen/{specimen.id}")
        self.assertEqual(obs.effectiveDateTime, "2026-09-30T10:00:00+00:00")

    def test_structured_indicator_emits_one_component_per_statistic(self):
        from oah_models.fhir import structured_indicator_to_fhir

        sample = a_sample()
        obs, _, _ = structured_indicator_to_fhir(
            StructuredIndicatorOah(
                sampleDetails=sample,
                type=CodeableConcept(coding=[Coding(code="nitrate", display="Nitrate")]),
                date=["2026-09-30T10:00:00+00:00"],
                performer=sample.performer,
                component=[
                    StructuredIndicatorComponent(
                        type=CodeableConcept(coding=[Coding(code="average")]), result=Quantity(value=14.2, unit="mg/L")
                    ),
                    StructuredIndicatorComponent(
                        type=CodeableConcept(coding=[Coding(code="maximum")]), result=Quantity(value=16.5, unit="mg/L")
                    ),
                ],
            )
        )
        self.assertIn("observation-with-component-oah", obs.meta.profile[0])
        self.assertEqual([c.code.coding[0].code for c in obs.component], ["average", "maximum"])
        self.assertEqual(obs.component[1].valueQuantity.value, 16.5)

    def test_multiple_dates_collapse_to_effective_period(self):
        from oah_models.fhir import simple_indicator_to_fhir

        sample = a_sample()
        obs, _, _ = simple_indicator_to_fhir(
            SimpleIndicatorOah(
                sampleDetails=sample,
                type=CodeableConcept(text="count"),
                date=["2026-09-30T10:00:00+00:00", "2026-01-01T00:00:00+00:00"],
                performer=sample.performer,
                result=Quantity(value=1),
            )
        )
        self.assertIsNone(obs.effectiveDateTime)
        self.assertTrue(obs.effectivePeriod.start.startswith("2026-01-01"))
        self.assertTrue(obs.effectivePeriod.end.startswith("2026-09-30"))


class HealthMeasureMapperTests(unittest.TestCase):
    def test_cohort_maps_to_observation_focus_not_subject(self):
        from oah_models.fhir import health_measure_to_fhir

        obs, location = health_measure_to_fhir(
            HealthMeasureOah(
                site=HealthMeasureSite(identifier=[Identifier(value="coimbra-d1")], name=["Coimbra district 1"]),
                dateOrPeriod=Period(start="2026-01-01T00:00:00+00:00", end="2026-09-27T00:00:00+00:00"),
                type=CodeableConcept(text="% with diabetes"),
                result=Quantity(value=8.1, unit="%"),
                cohort=Reference(reference="Group/group-coimbra-adults-18-64"),
            )
        )
        self.assertIn("observation-health-measure-oah", obs.meta.profile[0])
        self.assertEqual(obs.focus[0].reference, "Group/group-coimbra-adults-18-64")
        self.assertEqual(obs.subject.reference, f"Location/{location.id}")
        self.assertIsNone(obs.effectiveDateTime)
        self.assertTrue(obs.effectivePeriod.start.startswith("2026-01-01"))


if __name__ == "__main__":
    unittest.main()
