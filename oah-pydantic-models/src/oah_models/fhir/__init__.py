"""OAH -> FHIR mapper, implementing the ConceptMaps in oah/input/fsh/model-maps/*2FHIR.fsh."""

from .bundle import bundle_summary, dedupe, tag_resources, to_bundle
from .mappers import (
    cohort_to_fhir,
    dataset_to_fhir,
    health_indicators_to_fhir,
    health_measure_to_fhir,
    indicators_to_fhir,
    sample_to_fhir,
    simple_indicator_to_fhir,
    structured_indicator_to_fhir,
)
from .resources import (
    Device,
    Group,
    Library,
    Location,
    Observation,
    ObservationComponent,
    Organization,
    Practitioner,
    Specimen,
)

__all__ = [
    "cohort_to_fhir",
    "dataset_to_fhir",
    "health_indicators_to_fhir",
    "health_measure_to_fhir",
    "indicators_to_fhir",
    "sample_to_fhir",
    "simple_indicator_to_fhir",
    "structured_indicator_to_fhir",
    "Device",
    "Group",
    "Library",
    "Organization",
    "Practitioner",
    "Location",
    "to_bundle",
    "dedupe",
    "bundle_summary",
    "tag_resources",
    "Observation",
    "ObservationComponent",
    "Specimen",
]
