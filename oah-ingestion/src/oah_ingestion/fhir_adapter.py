"""Envelope -> OAH logical model -> FHIR R4.

This is the join between the two halves of the project. `envelope.py` validates
raw stream input; `oah_models` holds the OAH logical models; `oah_models.fhir`
maps those to profiled FHIR resources. Nothing previously connected them, so
validated events were printed and dropped. This module closes that gap.

Per stream:

| Envelope             | OAH model                        | FHIR profile                     |
|----------------------|----------------------------------|----------------------------------|
| `IOT_TELEMETRY`      | StructuredIndicator / SimpleIndicator | observation-with-component-oah / observation-indicators-oah |
| `CITIZEN_SURVEY`     | SimpleIndicator (coded result)   | observation-indicators-oah       |
| `PUBLIC_HEALTH`      | HealthMeasure (+ Group)          | observation-health-measure-oah   |

A measurement carrying any of `min_value`/`max_value`/`avg_value` becomes a
`StructuredIndicator` whose components are the Minimum/Maximum/Average slices
the IG's `observation-with-component-oah` defines; a bare reading becomes a
`SimpleIndicator`. That is the distinction those two profiles exist to draw, so
the choice is made from the data rather than hardcoded per stream.

Resource ids are deterministic (site + indicator + timestamp), so replaying the
same event upserts rather than duplicates -- see `oah_models.fhir.bundle`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from oah_models.common import CodeableConcept, Coding, Gps, Identifier, Quantity, Reference
from oah_models.fhir import (
    cohort_to_fhir,
    health_measure_to_fhir,
    simple_indicator_to_fhir,
    structured_indicator_to_fhir,
)
from oah_models.fhir import ObservationComponent
from oah_models.fhir.resources import (
    CODE_SYSTEM_URL,
    FHIRQuantity,
    Device,
    FHIRCodeableConcept,
    FHIRCoding,
    FHIRIdentifier,
    FHIRReference,
    HumanName,
    Organization,
    Practitioner,
)
from oah_models.health_measure import HealthMeasureOah, HealthMeasureSite
from oah_models.sample import SampleOah, SampleSite
from oah_models.simple_indicator import SimpleIndicatorOah
from oah_models.structured_indicator import StructuredIndicatorComponent, StructuredIndicatorOah

from .envelope import CitizenSurveyEnvelope, IoTEnvelope, PublicHealthEnvelope
from .sites import lookup

logger = logging.getLogger("OAH_FHIR_Adapter")

OAH_SITE_ID_SYSTEM = "https://oneaquahealth.eu/location-id"


def _slug(value: str) -> str:
    """FHIR `id` is `[A-Za-z0-9-.]{1,64}` -- same rule the mappers apply."""

    import re

    return (re.sub(r"[^A-Za-z0-9.-]+", "-", value.strip()).strip("-") or "id")[:64]

# UCUM where the OAH feeds use a UCUM-expressible unit. Units absent here are
# still carried as `Quantity.unit` free text -- a missing UCUM code is a
# terminology gap, not a reason to drop the measurement.
UCUM = {
    "mg/L": "mg/L",
    "mg NO3-N/L": "mg/L",
    "MPN/100mL": "{MPN}/dL",
    "ug/m3": "ug/m3",
    "Cel": "Cel",
    "%": "%",
    "pH": "[pH]",
    "/100000": "/100000",
    "{cases}": "{cases}",
}

# `StructuredIndicator.component` slice codes, per observation-with-component-oah.
COMPONENT_SLICES = (("avg_value", "average", "Average"), ("min_value", "minimum", "Minimum"), ("max_value", "maximum", "Maximum"))


def _quantity(value: float, unit: Optional[str]) -> Quantity:
    code = UCUM.get(unit) if unit else None
    return Quantity(
        value=value,
        unit=unit,
        system="http://unitsofmeasure.org" if code else None,
        code=code,
    )


def _oah_concept(code: str, display: Optional[str] = None) -> CodeableConcept:
    return CodeableConcept(coding=[Coding(system=CODE_SYSTEM_URL, code=code, display=display or code)])


def _sample_site(site_id: str, *, gps: Optional[Gps] = None, photo_urls: Optional[List[str]] = None) -> SampleSite:
    site = lookup(site_id)
    if gps is None and site.latitude is not None and site.longitude is not None:
        gps = Gps(latitude=site.latitude, longitude=site.longitude)
    return SampleSite(
        identifier=[Identifier(system=OAH_SITE_ID_SYSTEM, value=site_id)],
        name=[site.name],
        gps=gps,
        formReference=[Reference(reference=url, type="Binary") for url in (photo_urls or [])],
    )


def _sample(site_id: str, when: datetime, *, gps=None, photo_urls=None, performer=None) -> SampleOah:
    return SampleOah(
        site=_sample_site(site_id, gps=gps, photo_urls=photo_urls),
        dateOfSampling=when,
        performer=performer or [],
    )


def _stamp(obs, envelope, suffix: str) -> None:
    """Make the Observation id unique per event, not just per site+indicator.

    The mappers derive ids from site + indicator alone, which is right for a
    one-shot conversion but would make every reading from a station overwrite
    the previous one on upload. Appending the event timestamp keeps a time
    series while staying deterministic for replays of the *same* reading.
    """

    obs.id = f"{obs.id}-{int(envelope.timestamp.timestamp())}{suffix}"[:64]


# ---------------------------------------------------------------------------
# IOT_TELEMETRY
# ---------------------------------------------------------------------------


def iot_to_fhir(envelope: IoTEnvelope) -> List[object]:
    # FHIR R4 `Observation.performer` does not accept a Device (and neither does
    # `Specimen.collection.collector`), so the sensor is attached to
    # `Observation.device` after mapping rather than carried as an OAH performer.
    device_id = _slug(envelope.payload.device_id)
    device = FHIRReference(reference=f"Device/{device_id}", display=envelope.payload.device_id)
    sample = _sample(envelope.site_id, envelope.timestamp)
    resources: List[object] = [
        Device(
            id=device_id,
            identifier=[FHIRIdentifier(value=envelope.payload.device_id)],
            deviceName=[{"name": envelope.payload.device_id, "type": "user-friendly-name"}],
            type=FHIRCodeableConcept(
                coding=[FHIRCoding(system=CODE_SYSTEM_URL, code="water-quality-sensor", display="Water quality sensor")]
            ),
            location=FHIRReference(reference=f"Location/{_slug(envelope.site_id)}"),
        )
    ]

    for index, m in enumerate(envelope.payload.measurements):
        components = [
            StructuredIndicatorComponent(type=_oah_concept(code, display), result=_quantity(getattr(m, field), m.unit))
            for field, code, display in COMPONENT_SLICES
            if getattr(m, field) is not None
        ]

        if components:
            obs, location, specimen = structured_indicator_to_fhir(
                StructuredIndicatorOah(
                    sampleDetails=sample,
                    type=_oah_concept(m.parameter),
                    date=[envelope.timestamp],
                    performer=[],
                    # The spot reading sits alongside the summary statistics.
                    component=[
                        StructuredIndicatorComponent(type=_oah_concept("value", "Value"), result=_quantity(m.value, m.unit)),
                        *components,
                    ],
                )
            )
        else:
            obs, location, specimen = simple_indicator_to_fhir(
                SimpleIndicatorOah(
                    sampleDetails=sample,
                    type=_oah_concept(m.parameter),
                    date=[envelope.timestamp],
                    performer=[],
                    result=_quantity(m.value, m.unit),
                )
            )
        obs.device = device
        _stamp(obs, envelope, f"-{index}")
        resources.extend([obs, location, specimen])

    return resources


# ---------------------------------------------------------------------------
# CITIZEN_SURVEY
# ---------------------------------------------------------------------------


def citizen_survey_to_fhir(envelope: CitizenSurveyEnvelope) -> List[object]:
    payload = envelope.payload
    volunteer_id = _slug(payload.volunteer_id)
    volunteer = Reference(
        reference=f"Practitioner/{volunteer_id}",
        display=f"{payload.volunteer_id} via {payload.app_id}",
    )
    sample = _sample(
        envelope.site_id,
        envelope.timestamp,
        gps=Gps(latitude=payload.coordinates.latitude, longitude=payload.coordinates.longitude),
        photo_urls=payload.photo_urls,
        performer=[volunteer],
    )
    resources: List[object] = [
        Practitioner(
            id=volunteer_id,
            identifier=[FHIRIdentifier(system=f"https://oneaquahealth.eu/app/{payload.app_id}", value=payload.volunteer_id)],
            name=[HumanName(text=f"Citizen scientist {payload.volunteer_id}")],
        )
    ]

    for index, observation in enumerate(payload.observations):
        # A citizen survey answer is a coded value, not a number -- it maps to
        # Observation.valueCodeableConcept via SimpleIndicator.result.
        result = _oah_concept(observation.value_code)
        if observation.notes:
            result.text = observation.notes
        obs, location, specimen = simple_indicator_to_fhir(
            SimpleIndicatorOah(
                sampleDetails=sample,
                type=_oah_concept(observation.indicator),
                date=[envelope.timestamp],
                performer=[volunteer],
                result=result,
            )
        )
        _stamp(obs, envelope, f"-{index}")
        resources.extend([obs, location, specimen])

    return resources


# ---------------------------------------------------------------------------
# PUBLIC_HEALTH
# ---------------------------------------------------------------------------


def public_health_to_fhir(envelope: PublicHealthEnvelope) -> List[object]:
    payload = envelope.payload
    site = lookup(envelope.site_id)
    agency_id = _slug(payload.health_agency)
    agency = Reference(reference=f"Organization/{agency_id}", display=payload.health_agency)

    group = cohort_to_fhir(
        payload.cohort.group_id,
        age_range=payload.cohort.age_range,
        gender=payload.cohort.gender,
        location_reference=f"Location/{envelope.site_id}",
    )
    cohort_ref = Reference(reference=f"Group/{group.id}", display=payload.cohort.group_id)

    health_site = HealthMeasureSite(
        identifier=[Identifier(system=OAH_SITE_ID_SYSTEM, value=envelope.site_id)],
        name=[site.name],
        gps=(
            Gps(latitude=site.latitude, longitude=site.longitude)
            if site.latitude is not None and site.longitude is not None
            else None
        ),
        characteristics=[f"evaluation period {payload.evaluation_period}"],
    )

    resources: List[object] = [
        group,
        Organization(
            id=agency_id,
            identifier=[FHIRIdentifier(value=payload.health_agency)],
            name=payload.health_agency.replace("_", " "),
        ),
    ]

    # Risk scores describe the cohort -> observation-health-measure-oah.
    for index, risk in enumerate(payload.risk_scores):
        obs, location = health_measure_to_fhir(
            HealthMeasureOah(
                site=health_site,
                dateOrPeriod=envelope.timestamp,
                performer=[agency],
                type=_oah_concept(risk.indicator),
                result=Quantity(value=risk.score, unit="{score}", system="http://unitsofmeasure.org", code="{score}"),
                cohort=cohort_ref,
            )
        )
        # The agency's own LOW/MODERATE/HIGH reading of the score.
        obs.valueQuantity.unit = f"{{score}} ({risk.interpretation})"
        _stamp(obs, envelope, f"-r{index}")
        resources.extend([obs, location])

    # IDSP syndromic surveillance -> cohort health measures. The rate is the
    # Observation value; the raw case count and denominator ride along as
    # components so the figure stays auditable back to what was counted.
    for index, line in enumerate(payload.disease_surveillance):
        obs, location = health_measure_to_fhir(
            HealthMeasureOah(
                site=health_site,
                dateOrPeriod=envelope.timestamp,
                performer=[agency],
                type=_oah_concept(line.condition),
                result=Quantity(
                    value=line.rate_per_100k,
                    unit="per 100,000",
                    system="http://unitsofmeasure.org",
                    code="/100000",
                ),
                cohort=cohort_ref,
            )
        )
        obs.component = [
            ObservationComponent(
                code=FHIRCodeableConcept(coding=[FHIRCoding(system=CODE_SYSTEM_URL, code="cases", display="Cases reported")]),
                valueQuantity=FHIRQuantity(value=line.cases, unit="cases"),
            ),
            ObservationComponent(
                code=FHIRCodeableConcept(
                    coding=[FHIRCoding(system=CODE_SYSTEM_URL, code="populationAtRisk", display="Population at risk")]
                ),
                valueQuantity=FHIRQuantity(value=line.population_at_risk, unit="persons"),
            ),
        ]
        if line.baseline_rate_per_100k is not None:
            obs.component.append(
                ObservationComponent(
                    code=FHIRCodeableConcept(
                        coding=[FHIRCoding(system=CODE_SYSTEM_URL, code="baseline", display="Baseline rate")]
                    ),
                    valueQuantity=FHIRQuantity(value=line.baseline_rate_per_100k, unit="per 100,000"),
                )
            )
        _stamp(obs, envelope, f"-d{index}")
        resources.extend([obs, location])

    # Chemical summaries are environmental, not cohort measures -> they belong
    # on the site as indicators, under observation-indicators-oah.
    if payload.chemical_summaries:
        sample = _sample(envelope.site_id, envelope.timestamp, performer=[agency])
        for index, chem in enumerate(payload.chemical_summaries):
            obs, location, specimen = simple_indicator_to_fhir(
                SimpleIndicatorOah(
                    sampleDetails=sample,
                    type=_oah_concept(chem.indicator),
                    date=[envelope.timestamp],
                    performer=[agency],
                    result=_quantity(chem.value, chem.unit),
                )
            )
            _stamp(obs, envelope, f"-c{index}")
            resources.extend([obs, location, specimen])

    return resources


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_ADAPTERS = {
    "IOT_TELEMETRY": iot_to_fhir,
    "CITIZEN_SURVEY": citizen_survey_to_fhir,
    "PUBLIC_HEALTH": public_health_to_fhir,
}


def envelope_to_fhir(envelope) -> List[object]:
    """Convert any validated envelope to its profiled FHIR resources."""

    adapter = _ADAPTERS.get(envelope.source_type)
    if adapter is None:  # unreachable while the discriminated union is exhaustive
        raise ValueError(f"No FHIR adapter for source_type {envelope.source_type!r}")
    resources = adapter(envelope)
    logger.debug("Mapped %s event to %d FHIR resources", envelope.source_type, len(resources))
    return resources
