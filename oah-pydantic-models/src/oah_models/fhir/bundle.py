"""Bundle assembly for the OAH -> FHIR mappers.

The mapper functions in `mappers.py` each return loose resource objects, and
because resource `id`s are derived deterministically from the site identifier,
calling several of them for the same physical site yields duplicate
`Location`/`Specimen` resources. `README.md` documents de-duplicating by
`(resourceType, id)` by hand; this module does it for you and wraps the result
in a real FHIR `Bundle`.

Two bundle types are supported:

- `collection` -- a plain container, for local inspection or file handoff.
- `transaction` -- what you POST to a FHIR server. Each entry carries a
  `request` with `method: PUT` and `url: <ResourceType>/<id>`, which makes the
  upload **idempotent**: re-sending the same bundle updates the same resources
  instead of creating duplicates on every run. That matters because the
  mappers' ids are deterministic, so a replayed sensor reading should land on
  the same Observation rather than littering the server.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple


def dedupe(resources: Iterable[object]) -> List[object]:
    """Collapse resources sharing a `(resourceType, id)`, keeping the last seen."""

    seen: Dict[Tuple[str, str], object] = {}
    for resource in resources:
        if resource is None:
            continue
        seen[(resource.resourceType, resource.id)] = resource
    return list(seen.values())


def to_bundle(
    resources: Iterable[object], *, bundle_type: str = "transaction", base_url: Optional[str] = None
) -> dict:
    """Wrap resources in a FHIR Bundle, de-duplicated by `(resourceType, id)`.

    `transaction` bundles use conditional-free `PUT <Type>/<id>` requests so the
    same input always lands on the same server-side resource (idempotent
    upsert). `collection` bundles omit the `request` element entirely.

    `fullUrl` is only emitted when `base_url` is given, as the resource's
    absolute URL. It is deliberately omitted otherwise: `Bundle.entry.fullUrl`
    is 0..1, and a server rejects any non-absolute value that isn't a
    `urn:uuid:`/`urn:oid:` placeholder (HAPI-0533). Since these resources carry
    real, deterministic ids rather than placeholders, no `fullUrl` is the
    correct representation when the server base isn't known.
    """

    if bundle_type not in {"transaction", "collection"}:
        raise ValueError("bundle_type must be 'transaction' or 'collection'")

    entries = []
    for resource in dedupe(resources):
        entry = {"resource": resource.model_dump(exclude_none=True)}
        if base_url:
            entry["fullUrl"] = f"{base_url.rstrip('/')}/{resource.resourceType}/{resource.id}"
        if bundle_type == "transaction":
            entry["request"] = {"method": "PUT", "url": f"{resource.resourceType}/{resource.id}"}
        entries.append(entry)

    return {"resourceType": "Bundle", "type": bundle_type, "entry": entries}


def bundle_summary(bundle: dict) -> Dict[str, int]:
    """Count entries per resource type -- handy for logging what was uploaded."""

    counts: Dict[str, int] = {}
    for entry in bundle.get("entry", []):
        resource_type = entry["resource"]["resourceType"]
        counts[resource_type] = counts.get(resource_type, 0) + 1
    return dict(sorted(counts.items()))


def tag_resources(resources: Iterable[object], code: str, display: Optional[str] = None) -> List[object]:
    """Stamp every resource with a `meta.tag`, in place, and return them.

    Needed whenever the target server is shared. The public HAPI sandbox already
    carries OAH-profiled resources uploaded by other parties, so a search on
    `_profile` alone mixes their data into yours; tagging lets every query add
    `_tag=<system>|<code>` and get back exactly what this pipeline wrote.
    """

    from .resources import OAH_DATASET_TAG_SYSTEM, FHIRCoding

    tag = FHIRCoding(system=OAH_DATASET_TAG_SYSTEM, code=code, display=display or code)
    tagged = []
    for resource in resources:
        if resource is None:
            continue
        meta = getattr(resource, "meta", None)
        if meta is not None and not any(t.code == code for t in meta.tag):
            meta.tag.append(tag)
        tagged.append(resource)
    return tagged
