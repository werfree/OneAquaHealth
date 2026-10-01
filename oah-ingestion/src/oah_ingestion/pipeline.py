"""The end-to-end handoff: validated envelope -> FHIR resources -> FHIR server.

This is what every input channel calls. Before this existed, each worker's
terminal operation was `print(json.dumps(...))` and the event was dropped; the
`oah_models` FHIR mappers sat unreachable in a separate package. One function
now joins them:

    envelope -> envelope_to_fhir -> tag -> transaction Bundle -> POST

Failure policy: a FHIR upload failure is logged and reported, never raised into
the worker. A broker message should not be redelivered forever because a
downstream server is briefly down, and the normalized event is still printed
either way. Set `FHIR_UPLOAD_ENABLED=false` to run everything except the POST.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from oah_models.fhir import bundle_summary, tag_resources, to_bundle

from .alerts import raise_for
from .fhir_adapter import envelope_to_fhir
from .fhir_client import FhirError, base_url, upload_bundle, upload_enabled

logger = logging.getLogger("OAH_Pipeline")


def dataset_tag() -> str:
    """Tag applied to everything this pipeline writes, so queries can scope to it."""

    return os.getenv("OAH_DATASET_TAG", "oah-demo")


def print_generic_event(event: dict) -> None:
    """Print the normalized envelope -- retained as the human-readable trace."""

    print("\n--- Normalized ingestion event ---", flush=True)
    print(json.dumps(event, indent=2, ensure_ascii=False), flush=True)


def process(envelope, message: Optional[dict] = None) -> dict:
    """Normalize, convert to FHIR, and upload. Returns a result summary."""

    if message is not None:
        print_generic_event(message)

    # Screening runs before conversion: an operator should learn about an
    # exceedance even if the FHIR server is unreachable.
    alert = raise_for(envelope)

    try:
        resources = tag_resources(envelope_to_fhir(envelope), dataset_tag())
    except Exception:
        logger.exception("FHIR conversion failed for %s event", envelope.source_type)
        return {"fhir": "CONVERSION_FAILED", "uploaded": 0, "failed": 0, "alert": alert}

    bundle = to_bundle(resources, base_url=base_url())
    summary = bundle_summary(bundle)

    if not upload_enabled():
        logger.info("FHIR upload disabled; built %s (not sent)", summary)
        return {"fhir": "BUILT_NOT_SENT", "resources": summary, "uploaded": 0, "failed": 0, "alert": alert}

    try:
        uploaded, failed = upload_bundle(bundle)
    except FhirError as exc:
        logger.error("FHIR upload failed: %s", exc)
        return {"fhir": "UPLOAD_FAILED", "resources": summary, "uploaded": 0, "failed": len(bundle["entry"]), "alert": alert}

    logger.info(
        "FHIR upload -> %s: %d resource(s) %s", base_url(), uploaded, summary if failed == 0 else f"{summary} ({failed} failed)"
    )
    return {"fhir": "UPLOADED", "resources": summary, "uploaded": uploaded, "failed": failed, "alert": alert}
