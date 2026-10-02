"""Deterministic check that every number in an answer came from the data.

The assistant is told not to state figures it did not retrieve. Instructions
reduce fabrication; they do not prove its absence, and in a health context
"probably didn't make it up" is not a standard worth shipping. This module
checks it mechanically instead.

The method is simple and has no model in it: pull every numeric literal out of
the answer, pull every number out of the tool results that produced it, and
report any figure in the answer with no source. That is exactly the failure
already observed in this project -- an early version reported "above the safe
level of 10 mg/L", where 10 was a filter argument the model had chosen itself,
not a threshold from anywhere.

What this deliberately does NOT do:

- It does not judge whether the answer is *correct*, only whether its figures
  are *present in the retrieved data*. A number can be grounded and still be
  used in a wrong sentence.
- It does not catch fabricated prose. "Levels are rising" has no number in it
  and passes untouched; a single reading cannot show a trend, and only the
  prompt guards against that claim.

Both limits are real and are reported alongside the verdict rather than
papered over.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, List, Sequence, Set, Tuple

# Numbers written in prose: 0.611, 14.2, 6.4x, 1,200, 18-74.
#
# The lookbehind makes a leading "-" a sign only when it does not follow a
# digit. Without it the range "18-74" extracts as 18 and *minus* 74, so an
# answer saying "ages 18 to 74" would not match its own source data.
_NUMBER = re.compile(r"(?<![\d.])-?\d[\d,]*\.?\d*")

# Figures that carry no claim about the data and would only create noise:
# years, list ordinals, percentages of nothing, and the small integers that
# appear in ordinary phrasing ("the 3 stations", "both 2 cohorts").
_IGNORED_EXACT = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 100.0}


def _as_float(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def extract_numbers(text: str) -> List[float]:
    """Every numeric literal in a piece of text, as floats."""

    found = []
    for match in _NUMBER.finditer(text or ""):
        value = _as_float(match.group())
        if value is not None:
            found.append(value)
    return found


def _walk(node) -> Iterable[float]:
    """Every number anywhere inside a nested tool result."""

    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield float(node)
    elif isinstance(node, str):
        yield from extract_numbers(node)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)


def _supported(value: float, sources: Sequence[float], tolerance: float = 0.01) -> bool:
    """Is this figure in the retrieved data, allowing for rounding in prose?

    An answer may legitimately round 0.5341 to 0.53, or express 6.41 as 6.4.
    A relative tolerance accepts that; it will not accept a number that simply
    is not there.
    """

    for source in sources:
        if source == value:
            return True
        scale = max(abs(source), abs(value), 1e-9)
        if abs(source - value) / scale <= tolerance:
            return True
        # Derived ratios are legitimate: "6.4x the threshold" from 0.05 / 0.0078.
        if source != 0 and abs(value) > 1:
            for other in sources:
                if other and abs(abs(source / other) - abs(value)) / max(abs(value), 1e-9) <= tolerance:
                    return True
    return False


def check(answer: str, tool_results: Sequence[object], *, tolerance: float = 0.01) -> dict:
    """Verify an answer's figures against the tool results behind it.

    Returns a verdict dict with `grounded` (bool), the unsupported figures, and
    an explicit statement of what the check does not cover.
    """

    sources: Set[float] = set()
    for result in tool_results:
        sources.update(_walk(result))
    source_list = sorted(sources)

    claimed = extract_numbers(answer)
    unsupported = [
        value
        for value in claimed
        if value not in _IGNORED_EXACT and not _supported(value, source_list, tolerance)
    ]

    return {
        "grounded": not unsupported,
        "figures_in_answer": len(claimed),
        "figures_checked": len([v for v in claimed if v not in _IGNORED_EXACT]),
        "unsupported_figures": sorted(set(unsupported)),
        "source_figure_count": len(source_list),
        "not_covered": (
            "Checks numeric literals only. A grounded figure can still be used in a wrong sentence, "
            "and a claim with no number in it (for example a trend) is not checked at all."
        ),
    }


def format_verdict(verdict: dict) -> str:
    """One line for a terminal, stating the limit as well as the result."""

    if verdict["grounded"]:
        return (
            f"GROUNDED - all {verdict['figures_checked']} checked figure(s) appear in the retrieved data "
            f"({verdict['source_figure_count']} figures available). Numeric check only."
        )
    figures = ", ".join(f"{v:g}" for v in verdict["unsupported_figures"])
    return f"UNGROUNDED - {len(verdict['unsupported_figures'])} figure(s) not found in retrieved data: {figures}"
