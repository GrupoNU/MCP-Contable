"""Source-tier grounding system: the project's anti-hallucination guarantee.

Every value a connector returns to Claude MUST be wrapped by :func:`ground` so the
model (and the human reading the answer) can tell *where the data came from* and *how
much to trust it*. A connector must never hand back raw upstream data.

The trust model is a small, explicit ladder of "source tiers":

    Tier A  official structured API        -> trust as authoritative, no caveat
    Tier B  scraping of a predictable      -> usable, but flag for manual check
            official source
    Tier C  no connector available;        -> model knowledge only, must be verified
            model knowledge

The tier travels with the data all the way to the MCP tool boundary, where
:func:`to_dict` serializes it and attaches a human-readable ``citation_flag`` (see
:func:`verify_marker`). That flag is what keeps Claude honest about provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SourceTier(str, Enum):
    """Trust tier of the source a piece of data came from.

    Inherits from ``str`` so the value serializes cleanly to JSON (``"A"``) and can be
    compared against plain strings without extra ceremony.
    """

    A = "A"
    """Official structured API (e.g. ARCA via afip-ws, CKAN at datos.gob.ar /
    datos.jus.gob.ar). Authoritative; no verification caveat is added."""

    B = "B"
    """Scraping of a predictable official source (e.g. InfoLEG, Boletin Oficial,
    Santa Fe SIN). Reliable enough to use, but should be flagged for verification
    against the official source because page structure can change."""

    C = "C"
    """No connector available -- the answer rests on model knowledge alone.
    Must always be verified by a human before being relied upon."""


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (with timezone offset)."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GroundedResult:
    """A connector's payload wrapped with provenance metadata.

    Attributes
    ----------
    data:
        The actual payload returned by the connector. Any JSON-serializable value.
    source_tier:
        The :class:`SourceTier` describing how the data was obtained.
    source_url:
        URL (or stable identifier) of the upstream source the data came from.
    retrieved_at:
        ISO-8601 UTC timestamp stamped at wrap time. Set automatically by
        :func:`ground`; do not pass it by hand in normal use.
    notes:
        Optional free-text note (e.g. "field X inferred from heading"). Empty by
        default.
    """

    data: Any
    source_tier: SourceTier
    source_url: str
    retrieved_at: str = field(default_factory=_utc_now_iso)
    notes: str = ""


def ground(
    data: Any,
    tier: SourceTier,
    source_url: str,
    notes: str = "",
) -> GroundedResult:
    """Wrap raw connector data with provenance metadata.

    This is the single entry point every connector uses before returning anything.
    The ``retrieved_at`` timestamp is stamped here, at wrap time, in UTC.

    Parameters
    ----------
    data:
        The payload to wrap (any JSON-serializable value).
    tier:
        The :class:`SourceTier` for this data.
    source_url:
        URL or stable identifier of the upstream source.
    notes:
        Optional free-text provenance note.

    Returns
    -------
    GroundedResult
        Immutable wrapper carrying ``data`` plus provenance fields.
    """
    return GroundedResult(
        data=data,
        source_tier=tier,
        source_url=source_url,
        retrieved_at=_utc_now_iso(),
        notes=notes,
    )


def verify_marker(tier: SourceTier) -> str:
    """Return the human-readable verification marker for a tier.

    The marker is surfaced to Claude (as ``citation_flag``) so the model communicates
    the right level of confidence to the end user.

    Returns
    -------
    str
        - Tier A -> ``""`` (authoritative, no caveat needed)
        - Tier B -> ``"[scraped -- verificar contra fuente oficial]"``
        - Tier C -> ``"[verify]"``
    """
    if tier is SourceTier.A:
        return ""
    if tier is SourceTier.B:
        return "[scraped -- verificar contra fuente oficial]"
    if tier is SourceTier.C:
        return "[verify]"
    # Defensive: any future/unknown tier is treated as needing verification.
    return "[verify]"


def to_dict(result: GroundedResult) -> dict[str, Any]:
    """Serialize a :class:`GroundedResult` into the dict an MCP tool returns.

    The returned shape is the public contract every tool exposes to Claude::

        {
            "data": <payload>,
            "source_tier": "A" | "B" | "C",
            "source_url": "https://...",
            "retrieved_at": "2026-06-03T12:00:00+00:00",
            "notes": "",
            "citation_flag": "",          # computed via verify_marker(tier)
        }

    ``citation_flag`` is derived here so callers never have to remember to add it.
    """
    return {
        "data": result.data,
        "source_tier": result.source_tier.value,
        "source_url": result.source_url,
        "retrieved_at": result.retrieved_at,
        "notes": result.notes,
        "citation_flag": verify_marker(result.source_tier),
    }
