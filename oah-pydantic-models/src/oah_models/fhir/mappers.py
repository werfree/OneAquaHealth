"""OAH -> FHIR mappers.

Each function below implements one of the `*2FHIR.fsh` ConceptMap resources
in `oah/input/fsh/model-maps/`, field by field, exactly as declared there.
The docstring on each function names the source ConceptMap file and lists the
element mappings it implements, so it can be checked against that file
directly. Deviations from a literal reading (there are two, both noted
in `codes.py`) are called out explicitly rather than silently applied.

Design notes that follow from the ConceptMaps themselves, not invented here:

- `SampleOah2FHIR.fsh` maps `Sample` to three different targets (LocationOah,
  SpecimenOah, and directly to `Observation.subject`). So `sample_to_fhir`
  returns both a `Location` and a `Specimen`, and every Observation-producing
  mapper attaches `subject` (-> Location) and `specimen` (-> Specimen)
  per that ConceptMap, not just one or the other.
- `Sample.site.characteristics` and `Sample.site` (for Specimen) map with
  equivalence `relatedto` to the *resource as a whole*, not to any specific
  field. Nothing is synthesized for them here; that gap is real, not an
  oversight.
- `HealthMeasure.cohort` maps to `Observation.focus`; it is already a
  `Reference` on the Pydantic model, so no Group resource needs to be built
  here -- the cohort is assumed to already exist wherever it was defined.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Union

from ..common import CodeableConcept as OahCodeableConcept
from ..common import GenericIndicatorMeasure
from ..common import Identifier as OahIdentifier
from ..common import Period as OahPeriod
from ..common import Quantity as OahQuantity
from ..common import Reference as OahReference
from ..dataset import DataSetOah
from ..health_indicators import HealthIndicatorsOah
from ..health_measure import HealthMeasureOah
from ..indicators import IndicatorsOah
from ..sample import SampleOah
from ..simple_indicator import SimpleIndicatorOah
from ..structured_indicator import StructuredIndicatorOah
from . import codes as oah_codes
from .resources import (
    CODE_SYSTEM_URL,
    LIBRARY_NUMBER_OF_RECORDS_EXTENSION_URL,
    LIBRARY_SIZE_EXTENSION_URL,
    OBSERVATION_HEALTH_MEASURE_PROFILE,
    OBSERVATION_INDICATORS_PROFILE,
    OBSERVATION_WITH_COMPONENT_PROFILE,
    REFERENCE_FORM_EXTENSION_URL,
    FHIRAttachment,
    FHIRCodeableConcept,
    FHIRCoding,
    FHIRContactDetail,
    FHIRContactPoint,
    FHIRExtension,
    FHIRIdentifier,
    FHIRMeta,
    FHIRPeriod,
    FHIRPosition,
    FHIRQuantity,
    FHIRReference,
    FHIRRelatedArtifact,
    Library,
    Location,
    Observation,
    ObservationComponent,
    Specimen,
    SpecimenCollection,
)


def _slugify(value: str) -> str:
    """FHIR `id` is restricted to `[A-Za-z0-9\\-\\.]{1,64}`."""

    slug = re.sub(r"[^A-Za-z0-9.-]+", "-", value.strip()).strip("-")
    return (slug or "id")[:64]


def _fhir_codeable_concept(cc: Optional[OahCodeableConcept]) -> Optional[FHIRCodeableConcept]:
    if cc is None:
        return None
    return FHIRCodeableConcept(
        coding=[FHIRCoding(system=c.system, code=c.code, display=c.display) for c in cc.coding],
        text=cc.text,
    )


def _fhir_quantity(q: Optional[OahQuantity]) -> Optional[FHIRQuantity]:
    if q is None:
        return None
    return FHIRQuantity(value=q.value, unit=q.unit, system=q.system, code=q.code)


def _fhir_identifier(i: OahIdentifier) -> FHIRIdentifier:
    return FHIRIdentifier(system=i.system, value=i.value)


def _fhir_reference(r: Optional[OahReference]) -> Optional[FHIRReference]:
    if r is None:
        return None
    return FHIRReference(reference=r.reference, type=r.type, display=r.display)


def _value_x(value: Union[OahCodeableConcept, OahQuantity, str]) -> dict:
    """`result[x]` / `value[x]` -> FHIR choice-type kwargs (`value<Type>`)."""

    if isinstance(value, OahQuantity):
        return {"valueQuantity": _fhir_quantity(value)}
    if isinstance(value, OahCodeableConcept):
        return {"valueCodeableConcept": _fhir_codeable_concept(value)}
    if isinstance(value, str):
        return {"valueCodeableConcept": FHIRCodeableConcept(text=value)}
    raise TypeError(f"Unsupported result/value type: {type(value)!r}")


def _slug_for_concept(cc: OahCodeableConcept) -> str:
    if cc.coding and (cc.coding[0].code or cc.coding[0].display):
        return _slugify(cc.coding[0].code or cc.coding[0].display)
    if cc.text:
        return _slugify(cc.text)
    return "indicator"


# ---------------------------------------------------------------------------
# SampleOah2FHIR.fsh: Sample -> LocationOah, Sample -> SpecimenOah (+ Sample
# -> Observation.subject, implemented at the call sites in the Observation
# mappers below since it targets an Observation field directly).
# ---------------------------------------------------------------------------


def sample_to_fhir(sample: SampleOah) -> Tuple[Location, Specimen]:
    """Sample.site -> Location (relatedto); Sample.site.identifier -> Location.identifier
    (equivalent); Sample.site.name -> Location.name (equivalent); Sample.site.gps ->
    Location.position (equivalent); Sample.site.formReference ->
    Location.extension:referenceForm (equivalent). Sample.site ->
    Specimen.subject (relatedto, "if Specimen is used"); Sample.dateOfSampling
    -> Specimen.collection.collectedDateTime (equivalent, single point in
    time); Sample.performer[x] -> Specimen.collection.collector (equivalent).

    NOT mapped, because the ConceptMap declares no specific target field for
    them (equivalence `relatedto` to the resource as a whole, not a field):
    `Sample.site.characteristics`.
    """

    site = sample.site
    primary_id = site.identifier[0].value if site.identifier else site.name[0]
    location_id = _slugify(primary_id)

    location = Location(
        id=location_id,
        identifier=[_fhir_identifier(i) for i in site.identifier],
        name=site.name[0] if site.name else None,
        position=(
            FHIRPosition(longitude=site.gps.longitude, latitude=site.gps.latitude, altitude=site.gps.altitude)
            if site.gps
            else None
        ),
        extension=[
            FHIRExtension(
                url=REFERENCE_FORM_EXTENSION_URL,
                valueRelatedArtifact=FHIRRelatedArtifact(url=ref.reference, display=ref.display),
            )
            for ref in site.formReference
        ],
    )

    specimen = Specimen(
        id=f"{location_id}-specimen",
        subject=FHIRReference(reference=f"Location/{location_id}"),
        collection=SpecimenCollection(
            collector=_fhir_reference(sample.performer[0]) if sample.performer else None,
            collectedDateTime=sample.dateOfSampling.isoformat(),
        ),
    )
    return location, specimen


# ---------------------------------------------------------------------------
# SimpleIndicatorOah2FHIR.fsh: SimpleIndicator -> observation-indicators-oah
# ---------------------------------------------------------------------------


def simple_indicator_to_fhir(indicator: SimpleIndicatorOah) -> Tuple[Observation, Location, Specimen]:
    """SimpleIndicator.sampleDetails -> Observation.subject + Observation.specimen
    (both relatedto); SimpleIndicator.type -> Observation.code (equivalent);
    SimpleIndicator.date -> Observation.effective[x] (equivalent);
    SimpleIndicator.performer[x] -> Observation.performer (equivalent);
    SimpleIndicator.result[x] -> Observation.value[x] (equivalent).
    """

    location, specimen = sample_to_fhir(indicator.sampleDetails)
    obs = Observation(
        id=f"{location.id}-{_slug_for_concept(indicator.type)}",
        meta=FHIRMeta(profile=[OBSERVATION_INDICATORS_PROFILE]),
        code=_fhir_codeable_concept(indicator.type),
        subject=FHIRReference(reference=f"Location/{location.id}"),
        specimen=FHIRReference(reference=f"Specimen/{specimen.id}"),
        performer=[ref for ref in (_fhir_reference(p) for p in indicator.performer) if ref is not None],
        **_value_x(indicator.result),
    )
    if len(indicator.date) == 1:
        obs.effectiveDateTime = indicator.date[0].isoformat()
    elif len(indicator.date) > 1:
        obs.effectivePeriod = FHIRPeriod(start=min(indicator.date).isoformat(), end=max(indicator.date).isoformat())
    return obs, location, specimen


# ---------------------------------------------------------------------------
# StructuredIndicatorOah2FHIR.fsh: StructuredIndicator -> observation-with-component-oah
# ---------------------------------------------------------------------------


def structured_indicator_to_fhir(indicator: StructuredIndicatorOah) -> Tuple[Observation, Location, Specimen]:
    """StructuredIndicator.sampleDetails -> Observation.subject + Observation.specimen
    (both relatedto); StructuredIndicator.type -> Observation.code (equivalent);
    StructuredIndicator.date -> Observation.effective[x] (equivalent);
    StructuredIndicator.performer[x] -> Observation.performer (equivalent);
    StructuredIndicator.component -> Observation.component (relatedto);
    StructuredIndicator.component.type -> Observation.component.code
    (equivalent); StructuredIndicator.component.result[x] ->
    Observation.component.value[x] (equivalent).
    """

    location, specimen = sample_to_fhir(indicator.sampleDetails)
    components = [
        ObservationComponent(code=_fhir_codeable_concept(comp.type), **_value_x(comp.result))
        for comp in indicator.component
    ]

    obs = Observation(
        id=f"{location.id}-{_slug_for_concept(indicator.type)}",
        meta=FHIRMeta(profile=[OBSERVATION_WITH_COMPONENT_PROFILE]),
        code=_fhir_codeable_concept(indicator.type),
        subject=FHIRReference(reference=f"Location/{location.id}"),
        specimen=FHIRReference(reference=f"Specimen/{specimen.id}"),
        performer=[ref for ref in (_fhir_reference(p) for p in indicator.performer) if ref is not None],
        component=components,
    )
    if len(indicator.date) == 1:
        obs.effectiveDateTime = indicator.date[0].isoformat()
    elif len(indicator.date) > 1:
        obs.effectivePeriod = FHIRPeriod(start=min(indicator.date).isoformat(), end=max(indicator.date).isoformat())
    return obs, location, specimen


# ---------------------------------------------------------------------------
# HealthMeasureOah2FHIR.fsh: HealthMeasure -> observation-health-measure-oah
# ---------------------------------------------------------------------------


def health_measure_to_fhir(
    measure: HealthMeasureOah, *, code_override: Optional[Tuple[str, str]] = None
) -> Tuple[Observation, Location]:
    """HealthMeasure.site (+ .identifier/.name/.gps/.characteristics) -> Observation.subject
    (relatedto, "realized by the subject and the specimen elements");
    HealthMeasure.dateOrPeriod[x] -> Observation.effective[x] (equivalent);
    HealthMeasure.performer[x] -> Observation.performer (equivalent);
    HealthMeasure.type -> Observation.code (equivalent); HealthMeasure.result[x]
    -> Observation.value[x] (equivalent); HealthMeasure.cohort ->
    Observation.focus (equivalent).

    `code_override` is used by `health_indicators_to_fhir`: when a
    `HealthMeasure` comes from a named leaf of `HealthIndicatorsOah` (e.g.
    `diseasePrevalence.borrelia`), the OAH code is known from that field name
    (see codes.py) rather than from `measure.type`, which the source data may
    leave as free text.
    """

    site = measure.site
    primary_id = site.identifier[0].value if site.identifier else site.name[0]
    location_id = _slugify(primary_id)
    location = Location(
        id=location_id,
        identifier=[_fhir_identifier(i) for i in site.identifier],
        name=site.name[0] if site.name else None,
        position=(
            FHIRPosition(longitude=site.gps.longitude, latitude=site.gps.latitude, altitude=site.gps.altitude)
            if site.gps
            else None
        ),
    )

    if code_override is not None:
        code, display = code_override
        concept = FHIRCodeableConcept(coding=[FHIRCoding(system=CODE_SYSTEM_URL, code=code, display=display)])
        obs_id = f"{location_id}-{code}"
    else:
        concept = _fhir_codeable_concept(measure.type)
        obs_id = f"{location_id}-{_slug_for_concept(measure.type)}"

    obs = Observation(
        id=obs_id,
        meta=FHIRMeta(profile=[OBSERVATION_HEALTH_MEASURE_PROFILE]),
        code=concept,
        subject=FHIRReference(reference=f"Location/{location_id}"),
        focus=[ref for ref in [_fhir_reference(measure.cohort)] if ref is not None],
        performer=[ref for ref in (_fhir_reference(p) for p in measure.performer) if ref is not None],
        **_value_x(measure.result),
    )
    if isinstance(measure.dateOrPeriod, OahPeriod):
        obs.effectivePeriod = FHIRPeriod(
            start=measure.dateOrPeriod.start.isoformat() if measure.dateOrPeriod.start else None,
            end=measure.dateOrPeriod.end.isoformat() if measure.dateOrPeriod.end else None,
        )
    else:
        obs.effectiveDateTime = measure.dateOrPeriod.isoformat()

    return obs, location


# ---------------------------------------------------------------------------
# HealthIndicatorsOah2FHIR.fsh: HealthIndicators.{diseasePrevalence,
# causesOfDeath, hospitalization}.<leaf> -> Observation (relatedto), one
# Observation per HealthMeasure in each leaf list. The code system to use for
# each leaf's Observation.code is not restated in this ConceptMap; it follows
# the field-name-as-code convention IndicatorsOah2FHIR.fsh states explicitly
# for the sibling model (see codes.py).
# ---------------------------------------------------------------------------


def health_indicators_to_fhir(indicators: HealthIndicatorsOah) -> List[Tuple[Observation, Location]]:
    results: List[Tuple[Observation, Location]] = []
    for group in indicators.diseasePrevalence:
        results.extend(_map_health_measure_group(group, oah_codes.DISEASE_PREVALENCE_DISPLAY))
    for group in indicators.causesOfDeath:
        results.extend(_map_health_measure_group(group, oah_codes.CAUSES_OF_DEATH_DISPLAY))
    for group in indicators.hospitalization:
        results.extend(_map_health_measure_group(group, oah_codes.HOSPITALIZATION_DISPLAY))
    return results


def _map_health_measure_group(group, display_lookup: Dict[str, str]) -> List[Tuple[Observation, Location]]:
    results = []
    for field_name, display in display_lookup.items():
        for measure in getattr(group, field_name):
            results.append(health_measure_to_fhir(measure, code_override=(field_name, display)))
    return results


# ---------------------------------------------------------------------------
# IndicatorsOah2FHIR.fsh: IndicatorsOah.biological.{macroinvertebreates,
# diatomes, fishes} + .macrophytes/.riparianVegetation reuse
# SimpleIndicator/StructuredIndicator (per their own ConceptMaps, unchanged).
# The remaining `Base`-typed leaves map to Observation "where Observation.code
# is '<fieldName>'" -- see codes.py for the two known field/code-system
# mismatches and the `remote.*` copy-paste bug this module works around.
# ---------------------------------------------------------------------------


def indicators_to_fhir(
    indicators: IndicatorsOah, *, subject: Optional[FHIRReference] = None
) -> Tuple[List[Tuple[Observation, Location, Specimen]], List[Observation]]:
    """Returns `(sample_based, generic_based)`.

    `sample_based` comes from the `SimpleIndicator`/`StructuredIndicator`
    leaves, each with its own `Location`/`Specimen` built from its
    `sampleDetails` (via `simple_indicator_to_fhir`/`structured_indicator_to_fhir`).

    `generic_based` comes from the `GenericIndicatorMeasure` leaves
    (hydromorphological/water/bioRisk/remote + biological.microbiomes), which
    carry no site of their own -- `IndicatorsOah` has no site/sample context
    at that level, so these Observations get `subject=subject` if the caller
    supplies one (e.g. the same site the sample-based indicators in this same
    collection event were measured at), and are left without a `subject`
    otherwise. `observation-indicators-oah` requires `subject 1..`, so an
    unset `subject` here is a known non-conformance until the caller supplies
    one -- not a bug in this mapper, but a real gap in what
    `GenericIndicatorMeasure` captures (see oah/REUSE-GUIDE.md).
    """

    sample_based: List[Tuple[Observation, Location, Specimen]] = []
    generic_based: List[Observation] = []

    bio = indicators.biological
    if bio:
        for ind in [*bio.macroinvertebreates, *bio.diatomes, *bio.fishes]:
            sample_based.append(simple_indicator_to_fhir(ind))
        for ind in [*bio.macrophytes, *bio.riparianVegetation]:
            sample_based.append(structured_indicator_to_fhir(ind))
        generic_based.extend(
            _map_generic_measures(bio.microbiomes, "microbiomes", oah_codes.BIOLOGICAL_MICROBIOMES_DISPLAY, subject)
        )

    for group_model, display_lookup in (
        (indicators.hydromorphological, oah_codes.HYDROMORPHOLOGICAL_DISPLAY),
        (indicators.water, oah_codes.WATER_DISPLAY),
        (indicators.bioRisk, oah_codes.BIO_RISK_DISPLAY),
        (indicators.remote, oah_codes.REMOTE_SENSING_DISPLAY),
    ):
        if group_model is None:
            continue
        for field_name, display in display_lookup.items():
            measures = getattr(group_model, field_name)
            generic_based.extend(_map_generic_measures(measures, field_name, display, subject))

    return sample_based, generic_based


def _map_generic_measures(
    measures: List[GenericIndicatorMeasure],
    code: str,
    display: str,
    subject: Optional[FHIRReference],
) -> List[Observation]:
    observations = []
    for i, measure in enumerate(measures):
        is_numeric = isinstance(measure.value, (int, float)) and not isinstance(measure.value, bool)
        if is_numeric and measure.unit:
            value_kwargs = {"valueQuantity": FHIRQuantity(value=float(measure.value), unit=measure.unit)}
        elif measure.value is not None:
            value_kwargs = {"valueCodeableConcept": FHIRCodeableConcept(text=str(measure.value))}
        else:
            value_kwargs = {}
        observations.append(
            Observation(
                id=_slugify(f"{code}-{i}"),
                meta=FHIRMeta(profile=[OBSERVATION_INDICATORS_PROFILE]),
                code=FHIRCodeableConcept(coding=[FHIRCoding(system=CODE_SYSTEM_URL, code=code, display=display)]),
                subject=subject,
                effectiveDateTime=measure.date.isoformat() if measure.date else None,
                **value_kwargs,
            )
        )
    return observations


# ---------------------------------------------------------------------------
# DataSetOah2FHIR.fsh: DataSet -> LibraryOah (+ DataSet.record -> Attachment,
# nested inside Library.content). DataSet.record.format -> DataRequirement
# (type/profile, "As FHIR resource"/"As FHIR profile") is declared but too
# underspecified to implement meaningfully and is intentionally left out.
# ---------------------------------------------------------------------------


def dataset_to_fhir(dataset: DataSetOah) -> Library:
    """DataSet.pid -> Library.url; DataSet.title -> Library.title;
    DataSet.description -> Library.description; DataSet.version ->
    Library.version; DataSet.type -> Library.type; DataSet.contact ->
    Library.contact; DataSet.publisher -> Library.publisher; DataSet.author ->
    Library.author; DataSet.date -> Library.date; DataSet.dateOfApproval ->
    Library.approvalDate; DataSet.dateOfReview -> Library.lastReviewDate;
    DataSet.copyright -> Library.copyright; DataSet.size ->
    Library.extension:size; DataSet.numberOfRecords ->
    Library.extension:numberOfRecords; DataSet.record -> Library.content
    (each record additionally: .title -> Attachment.title, .format ->
    Attachment.contentType, .link -> Attachment.url, .size -> Attachment.size).
    """

    library = Library(
        id=_slugify(dataset.pid.rsplit("/", 1)[-1] or dataset.pid),
        url=dataset.pid,
        title=dataset.title,
        description="; ".join(dataset.description) or None,
        version=dataset.version,
        type=_fhir_codeable_concept(dataset.type),
        contact=[
            FHIRContactDetail(name=c.name, telecom=[FHIRContactPoint(value=t) for t in c.telecom])
            for c in dataset.contact
        ],
        publisher=dataset.publisher,
        author=[
            FHIRContactDetail(name=a.name, telecom=[FHIRContactPoint(value=t) for t in a.telecom])
            for a in dataset.author
        ],
        date=dataset.date.isoformat() if dataset.date else None,
        approvalDate=dataset.dateOfApproval.isoformat() if dataset.dateOfApproval else None,
        lastReviewDate=dataset.dateOfReview.isoformat() if dataset.dateOfReview else None,
        copyright="; ".join(dataset.copyright) or None,
        content=[
            FHIRAttachment(contentType=r.format, url=r.link, title=r.title, size=r.size.value if r.size else None)
            for r in dataset.record
        ],
    )
    if dataset.size is not None:
        library.extension.append(FHIRExtension(url=LIBRARY_SIZE_EXTENSION_URL, valueQuantity=_fhir_quantity(dataset.size)))
    if dataset.numberOfRecords is not None:
        library.extension.append(
            FHIRExtension(url=LIBRARY_NUMBER_OF_RECORDS_EXTENSION_URL, valueInteger=dataset.numberOfRecords)
        )
    return library
