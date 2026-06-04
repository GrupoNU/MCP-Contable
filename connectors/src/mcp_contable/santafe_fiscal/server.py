"""FastMCP server for the Santa Fe fiscal calendar (Tier B, SCRAPER).

This connector reads the Province of Santa Fe's **Calendarios Impositivos** index page
(``santafe.gob.ar/.../view/full/111353``), which lists the tax-due-date calendar of each
fiscal year (Ingresos Brutos and other provincial taxes). There is NO structured API, so
this is a Tier B source: every result carries ``[scraped -- verificar contra fuente
oficial]`` automatically.

HONEST SCOPE (verified live against the site, 2026-06)
======================================================
What is reliably available in the **static HTML** is the *index*: a list of
``"Calendario año <YYYY>"`` entries, each linking to that year's official calendar page on
the provincial site. We parse that index robustly.

What is NOT in the static HTML: the per-year calendar pages do NOT expose the individual
due dates as parseable tables, PDFs or text -- that detail is rendered client-side / lives
behind the page. So this connector does NOT fabricate due dates. Instead:

    * ``santafe_fiscal_list_calendarios`` returns the year -> official-URL index.
    * ``santafe_fiscal_get_calendario`` returns the official URL of a given year's
      calendar plus an explicit note that the detailed due dates must be consulted at that
      URL (they are not extractable from the static HTML).

This keeps the connector useful (it gives the authoritative source URL with provenance)
without inventing dates -- which in accounting is the cardinal sin (see docs/GROUNDING.md).

Design rules honored here (see connectors/CLAUDE.md):

    * All HTTP goes through ``common.fetch`` -- never instantiate ``httpx`` directly.
    * Every tool returns ``to_dict(ground(...))`` with ``SourceTier.B`` -- never raw HTML.
    * Tools NEVER raise to the MCP boundary; failures become grounded, explained results.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin

from fastmcp import FastMCP
from selectolax.parser import HTMLParser

from mcp_contable.common import (
    SourceResponseError,
    SourceTier,
    SourceUnavailableError,
    TTLCache,
    fetch,
    ground,
    to_dict,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Base host of the Santa Fe provincial site.
SF_BASE = "https://www.santafe.gob.ar"

#: The "Calendarios Impositivos" index page (lists one calendar per fiscal year).
CALENDARIOS_INDEX_URL = (
    f"{SF_BASE}/index.php/web/content/view/full/111353"
)

#: Tier for this whole connector: HTML scrape of a predictable official source.
TIER = SourceTier.B

#: Per-request timeout (seconds).
HTTP_TIMEOUT = 30.0

#: TTL: the index changes about once a year; cache generously.
_CACHE_TTL = 3600.0

#: Process-local cache. Safe per common/cache.py (single event loop, no persistence).
_cache = TTLCache(default_ttl=_CACHE_TTL)

mcp = FastMCP("santafe-fiscal")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _error(
    message: str,
    source_url: str,
    *,
    detail: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a grounded error result (same envelope as a success, never raises)."""
    payload: dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    note = f"Santa Fe fiscal calendar request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, source_url, notes=note))


def _clean(text: Optional[str]) -> str:
    """Collapse runs of whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _parse_index(html: str) -> list[dict[str, Any]]:
    """Parse the calendars index into a list of ``{anio, titulo, url}`` entries.

    Each calendar link on the index page has the form
    ``/index.php/web/content/view/full/<ID>/(subtema)/111353`` and anchor text like
    "Calendario año 2026". We extract the year from the anchor text and absolutize the
    URL. Entries without a 4-digit year in their text (e.g. "Calendarios de años
    anteriores", "Calendario de Feriados") are skipped so the result is strictly the
    per-year tax calendars.
    """
    tree = HTMLParser(html)
    entries: list[dict[str, Any]] = []
    seen_years: set[str] = set()
    for a in tree.css("a"):
        href = a.attributes.get("href") or ""
        if "(subtema)/111353" not in href:
            continue
        text = _clean(a.text())
        # Only the yearly tax calendars: "Calendario año 2026" (skip feriados, etc.).
        if "feriado" in text.lower():
            continue
        m = re.search(r"calendario\s+a[nñ]o\s+(\d{4})", text, flags=re.IGNORECASE)
        if not m:
            continue
        anio = m.group(1)
        if anio in seen_years:
            continue
        seen_years.add(anio)
        entries.append(
            {
                "anio": anio,
                "titulo": text,
                "url": urljoin(SF_BASE, href),
            }
        )
    # Most-recent year first.
    entries.sort(key=lambda e: e["anio"], reverse=True)
    return entries


async def _fetch_index() -> tuple[Optional[list[dict[str, Any]]], Optional[dict[str, Any]]]:
    """Fetch and parse the calendars index, returning ``(entries, error_dict)``."""
    cache_key = ("index",)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached, None

    try:
        response = await fetch(CALENDARIOS_INDEX_URL, timeout=HTTP_TIMEOUT)
    except SourceUnavailableError as exc:
        return None, _error("source unavailable", CALENDARIOS_INDEX_URL, detail=str(exc))
    except SourceResponseError as exc:
        return None, _error(
            f"upstream returned HTTP {exc.status_code}",
            CALENDARIOS_INDEX_URL,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )

    # The provincial site serves ISO-8859-1; decode accordingly for accented text.
    if not response.encoding:
        response.encoding = "iso-8859-1"
    entries = _parse_index(response.text)
    if not entries:
        return None, _error(
            "no calendars found on index page",
            CALENDARIOS_INDEX_URL,
            detail="the page structure may have changed",
        )
    _cache.set(cache_key, entries)
    return entries, None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def santafe_fiscal_list_calendarios() -> dict[str, Any]:
    """List the available Santa Fe fiscal-year tax calendars (Ingresos Brutos, etc.).

    Scrapes the provincial "Calendarios Impositivos" index (Tier B) and returns one entry
    per fiscal year, each with the official URL of that year's calendar. Use
    ``santafe_fiscal_get_calendario(anio)`` to get the official URL for a specific year.

    The detailed due dates themselves are published on each year's official page (not
    extractable from the static HTML), so this tool returns the authoritative URLs rather
    than fabricated dates.

    Returns
    -------
    dict
        Grounded result (``source_tier="B"``) whose ``data`` is
        ``{"count": int, "calendarios": [{anio, titulo, url}, ...]}`` (most recent first).
    """
    entries, err = await _fetch_index()
    if err is not None:
        return err
    return to_dict(
        ground(
            {"count": len(entries), "calendarios": entries},
            TIER,
            CALENDARIOS_INDEX_URL,
            notes=(
                "Index of Santa Fe provincial tax calendars (one per fiscal year). The "
                "individual due dates are on each year's official URL; they are not "
                "extracted here to avoid fabricating dates."
            ),
        )
    )


@mcp.tool
async def santafe_fiscal_get_calendario(anio: str) -> dict[str, Any]:
    """Get the official URL of the Santa Fe tax calendar for a given fiscal year.

    Looks up ``anio`` (e.g. "2026") in the provincial calendars index (Tier B) and returns
    the official page URL where that year's Ingresos Brutos / provincial-tax due dates are
    published.

    IMPORTANT (honest limitation): the individual due dates are NOT returned, because they
    are not available in the page's static HTML. This tool gives you the authoritative URL
    to consult them. Never state a Santa Fe due date without checking that official page.

    Parameters
    ----------
    anio:
        The fiscal year, 4 digits, e.g. ``"2026"``.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{anio, titulo, url, detail_available: false}``
        when found, or an ``{"error": ...}`` payload when the year is not listed.
    """
    anio = (anio or "").strip()
    if not re.fullmatch(r"\d{4}", anio):
        return _error(
            "invalid anio",
            CALENDARIOS_INDEX_URL,
            detail='provide a 4-digit year, e.g. "2026"',
        )

    entries, err = await _fetch_index()
    if err is not None:
        return err

    match = next((e for e in entries if e["anio"] == anio), None)
    if match is None:
        available = [e["anio"] for e in entries]
        return _error(
            "calendar not found for that year",
            CALENDARIOS_INDEX_URL,
            detail=f"available years: {', '.join(available)}",
            extra={"available_years": available},
        )

    data = {
        "anio": match["anio"],
        "titulo": match["titulo"],
        "url": match["url"],
        # The static HTML does not expose the individual due dates; consult the URL.
        "detail_available": False,
        "message": (
            "The detailed Ingresos Brutos / provincial-tax due dates for this year are "
            "published on the official URL above and are not extractable from the static "
            "HTML. Consult that page; never state a due date without verifying it there."
        ),
    }
    return to_dict(
        ground(
            data,
            TIER,
            match["url"],
            notes=(
                "Official Santa Fe tax-calendar URL for the requested year (Tier B). Due "
                "dates not fabricated: verify them on the official page."
            ),
        )
    )


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
