"""Site gazetteer: `site_id` -> name and WGS84 position.

IoT telemetry and public-health envelopes identify a site by `site_id` only --
they carry no coordinates -- so the FHIR `Location` built from them would have
no `position` and could not be placed on a map. This module supplies that
position from `demo/sites.json`.

Citizen-survey envelopes *do* carry coordinates; those are authoritative and
the adapter passes them in directly rather than consulting this registry.

Point `OAH_SITES_FILE` at your own gazetteer to override the bundled demo one.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, NamedTuple, Optional

logger = logging.getLogger("OAH_Sites")

_DEFAULT_SITES_FILE = Path(__file__).resolve().parents[3] / "demo" / "sites.json"


class Site(NamedTuple):
    site_id: str
    name: str
    city: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    district: Optional[str] = None
    reach: Optional[str] = None


_registry: Optional[Dict[str, Site]] = None


def _load() -> Dict[str, Site]:
    path = Path(os.getenv("OAH_SITES_FILE", str(_DEFAULT_SITES_FILE)))
    if not path.is_file():
        logger.warning("Site gazetteer not found at %s; Locations will have no position", path)
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    sites = {}
    for site_id, entry in raw.get("sites", {}).items():
        sites[site_id] = Site(
            site_id=site_id,
            name=entry.get("name", site_id),
            city=entry.get("city"),
            latitude=entry.get("latitude"),
            longitude=entry.get("longitude"),
            district=entry.get("district"),
            reach=entry.get("reach"),
        )
    logger.info("Loaded %d sites from %s", len(sites), path)
    return sites


def registry() -> Dict[str, Site]:
    global _registry
    if _registry is None:
        _registry = _load()
    return _registry


def lookup(site_id: str) -> Site:
    """Return the registered site, or an unpositioned placeholder for unknown ids.

    An unknown site is not an error -- a new sensor should still ingest. It just
    produces a `Location` without `position`, which the GIS layer skips.
    """

    found = registry().get(site_id)
    if found is not None:
        return found
    return Site(site_id=site_id, name=site_id, city=None, latitude=None, longitude=None)


def reset_cache() -> None:
    """Drop the memoized registry (used by tests that swap `OAH_SITES_FILE`)."""

    global _registry
    _registry = None
