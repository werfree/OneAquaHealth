"""Threshold alerts raised at ingestion time.

`docs/plan.md` promises "real-time risk alerts", but nothing watched the stream:
events were validated, converted and uploaded, and an exceedance was only
visible to whoever went looking afterwards. This raises it as the reading
arrives.

Detection is **pure Python** and has no model in it. That is deliberate: an
alert that fires is an operational signal, and it must be reproducible,
instant, and free. A language model is involved only when someone asks for the
alert to be *explained*, which is `oah_agent.alerts.narrate`.

The pipeline must never fail because alerting failed. Every entry point here is
exception-safe; a broken handler loses the alert, not the reading.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from .thresholds import evaluate_many, severity_of

logger = logging.getLogger("OAH_Alerts")

# Public-health interpretations that count as elevated.
ELEVATED = {"MODERATE", "HIGH"}

_handlers: List[Callable[[dict], None]] = []


def subscribe(handler: Callable[[dict], None]) -> None:
    """Register a callback invoked for each alert (dashboard push, webhook, pager)."""

    _handlers.append(handler)


def _readings_from(envelope) -> List[dict]:
    """Flatten any envelope to `{indicator, value, unit}` for screening."""

    payload = envelope.payload
    source = envelope.source_type

    if source == "IOT_TELEMETRY":
        return [
            {"indicator": m.parameter, "value": m.value, "unit": m.unit} for m in payload.measurements
        ]
    if source == "PUBLIC_HEALTH":
        return [
            {"indicator": c.indicator, "value": c.value, "unit": c.unit} for c in payload.chemical_summaries
        ]
    # Citizen survey answers are coded, not numeric -- nothing to screen.
    return []


def _elevated_risks(envelope) -> List[dict]:
    if envelope.source_type != "PUBLIC_HEALTH":
        return []
    return [
        {"indicator": r.indicator, "score": r.score, "interpretation": r.interpretation}
        for r in envelope.payload.risk_scores
        if r.interpretation in ELEVATED
    ]


def assess(envelope) -> Optional[dict]:
    """Screen one envelope. Returns an alert, or None when nothing crossed.

    Severity is the agency's own interpretation where the stream supplies one,
    and is otherwise derived from how far past the screening value a reading
    sits -- never invented beyond what the data states.
    """

    exceedances = evaluate_many(_readings_from(envelope), city=envelope.city)
    risks = _elevated_risks(envelope)
    if not exceedances and not risks:
        return None

    if any(r["interpretation"] == "HIGH" for r in risks) or severity_of(exceedances, city=envelope.city) == "HIGH":
        severity = "HIGH"
    else:
        severity = "MODERATE"

    return {
        "severity": severity,
        "site_id": envelope.site_id,
        "city": envelope.city,
        "source_type": envelope.source_type,
        "observed_at": envelope.timestamp.isoformat(),
        "raised_at": datetime.now(timezone.utc).isoformat(),
        "exceedances": exceedances,
        "elevated_risks": risks,
        "caveat": (
            "Screening thresholds, not regulatory limits. A single reading is not a trend, and an "
            "environmental exceedance co-occurring with an elevated health score at one site is an "
            "association to investigate, not evidence of causation."
        ),
    }


def format_alert(alert: dict) -> str:
    """One-screen operator summary."""

    lines = [f"[{alert['severity']}] {alert['site_id']} ({alert['city']}) - {alert['observed_at']}"]
    for exceedance in alert["exceedances"]:
        factor = exceedance.get("exceedance_factor")
        suffix = f" ({factor}x threshold {exceedance['threshold']})" if factor else f" (outside {exceedance['threshold']})"
        lines.append(f"    ENV  {exceedance['indicator']}: {exceedance['value']} {exceedance['unit']}{suffix}")
    for risk in alert["elevated_risks"]:
        lines.append(f"    HLTH {risk['indicator']}: {risk['score']} [{risk['interpretation']}]")
    return "\n".join(lines)


def raise_for(envelope) -> Optional[dict]:
    """Assess an envelope and notify subscribers. Never raises."""

    try:
        alert = assess(envelope)
    except Exception:
        logger.exception("Alert assessment failed for %s event", getattr(envelope, "source_type", "?"))
        return None
    if alert is None:
        return None

    logger.warning("Threshold alert\n%s", format_alert(alert))
    for handler in _handlers:
        try:
            handler(alert)
        except Exception:
            logger.exception("Alert handler %r failed", getattr(handler, "__name__", handler))
    return alert
