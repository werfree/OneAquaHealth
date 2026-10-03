"""Minimal FHIR R4 REST client -- uploads OAH bundles and runs searches.

Targets the public HAPI FHIR sandbox (`https://hapi.fhir.org/baseR4`) by
default, which is what `docs/plan.md` names as the interoperability core.
Stdlib `urllib` only, matching the publisher package -- no new dependency.

Uploads go as **transaction bundles of conditional-free PUTs** (see
`oah_models.fhir.bundle`), so ingesting the same event twice updates the same
resources instead of creating duplicates. That is what makes a live demo
re-runnable.

Set `FHIR_BASE_URL` to point at your own server. Set `FHIR_UPLOAD_ENABLED=false`
to run the pipeline without any network call (the normalized event and the
bundle are still produced and logged).
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("OAH_FHIR_Client")

DEFAULT_BASE_URL = "https://hapi.fhir.org/baseR4"
FHIR_JSON = "application/fhir+json"


class FhirError(RuntimeError):
    """A FHIR server rejected the request or could not be reached."""


def base_url() -> str:
    return os.getenv("FHIR_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def upload_enabled() -> bool:
    return os.getenv("FHIR_UPLOAD_ENABLED", "true").strip().lower() not in {"false", "0", "no"}


# A shared public sandbox intermittently stalls under a long ingest run. A
# transient read timeout is not a reason to lose a reading, so transport-level
# failures are retried with backoff; an HTTP error (a rejected resource) is not
# retried, because sending it again will fail the same way.
RETRIES = int(os.getenv("FHIR_RETRIES", "3"))


def _request(method: str, url: str, body: Optional[bytes] = None, timeout: int = 60) -> dict:
    headers = {"Accept": FHIR_JSON, "Accept-Encoding": "gzip"}
    if body is not None:
        headers["Content-Type"] = FHIR_JSON

    last: Optional[Exception] = None
    for attempt in range(RETRIES):
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise FhirError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < RETRIES:
                wait = 2 ** attempt
                logger.warning("FHIR %s failed (%s); retrying in %ds", method, exc, wait)
                time.sleep(wait)

    raise FhirError(f"Cannot reach FHIR server at {url} after {RETRIES} attempts: {last}")


def upload_bundle(bundle: dict, *, timeout: int = 60) -> Tuple[int, int]:
    """POST a transaction bundle. Returns `(succeeded, failed)` entry counts.

    A FHIR transaction returns a `transaction-response` Bundle with one entry
    per request, each carrying its own status -- a 200 on the POST does not mean
    every resource landed. This inspects the per-entry statuses rather than
    trusting the envelope.
    """

    url = f"{base_url()}"
    response = _request("POST", url, json.dumps(bundle).encode("utf-8"), timeout=timeout)

    entries = response.get("entry", [])
    succeeded = failed = 0
    for entry in entries:
        status = str(entry.get("response", {}).get("status", ""))
        if status.startswith(("200", "201")):
            succeeded += 1
        else:
            failed += 1
            logger.warning("FHIR transaction entry failed: %s", status or entry)
    expected = len(bundle.get("entry", []))
    if len(entries) != expected:
        failed += abs(expected - len(entries))
    if not entries:
        logger.warning("FHIR server returned no transaction entries: %s", str(response)[:400])
    return succeeded, failed


MAX_PAGES = int(os.getenv("FHIR_MAX_PAGES", "6"))


def max_search_results() -> int:
    """Upper bound on resources one `search()` collects across all pages."""
    return int(os.getenv("FHIR_MAX_SEARCH_RESULTS", "5000"))


def _next_link(bundle: dict) -> Optional[str]:
    for link in bundle.get("link", []):
        if link.get("relation") == "next" and link.get("url"):
            return link["url"]
    return None


def search(
    resource_type: str,
    params: Dict[str, str],
    *,
    timeout: int = 30,
    paginate: bool = True,
    max_results: Optional[int] = None,
) -> List[dict]:
    """Run a FHIR search and return every matching resource.

    `params` are FHIR search parameters, e.g.
    `{"_profile": OBSERVATION_WITH_COMPONENT_PROFILE, "code": "nitrate"}`.

    Servers cap a page regardless of `_count` -- HAPI returns 500 however many
    you ask for -- so a single-page read silently truncates. That is a bad
    failure anywhere and a dangerous one here: with an ascending date sort the
    rows dropped are the most recent, so "the latest reading" came back days
    stale and every severity derived from it was wrong.

    Follow `Bundle.link` rel=next until the result set is exhausted, a repeated
    page URL is seen, `max_results` (default `FHIR_MAX_SEARCH_RESULTS`) is
    reached, or `MAX_PAGES` pages have been read. `paginate=False` reads only
    the first page.
    """

    limit = max_search_results() if max_results is None else max_results
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url: Optional[str] = f"{base_url()}/{resource_type}?{query}"
    resources: List[dict] = []
    seen_urls = set()

    for _ in range(MAX_PAGES):
        if not url or url in seen_urls or len(resources) >= limit:
            break
        seen_urls.add(url)
        logger.debug("FHIR GET %s", url)
        bundle = _request("GET", url, timeout=timeout)
        resources.extend(entry["resource"] for entry in bundle.get("entry", []) if "resource" in entry)
        if not paginate:
            break
        url = _next_link(bundle)
    else:
        logger.warning("Stopped after %d pages for %s; result may be incomplete", MAX_PAGES, resource_type)

    if len(resources) >= limit:
        logger.warning("FHIR search for %s stopped at %d resources (FHIR_MAX_SEARCH_RESULTS)", resource_type, limit)
        return resources[:limit]
    return resources


def search_url(resource_type: str, params: Dict[str, str]) -> str:
    """The URL `search()` would call -- shown to users so a query is auditable."""

    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return f"{base_url()}/{resource_type}?{query}"


def capabilities(*, timeout: int = 30) -> dict:
    """Fetch the server's CapabilityStatement -- a cheap reachability check."""

    return _request("GET", f"{base_url()}/metadata?_summary=true", timeout=timeout)
