"""FastMCP server for the Boletin Oficial de la Republica Argentina (Tier B, SCRAPER).

This connector reads avisos published on ``boletinoficial.gob.ar``. In MCP-Contable it
is most useful to read **Resoluciones Generales (RG) de ARCA** (ex-AFIP) and other fiscal
norms published in the Boletin Oficial by their aviso id + date + section. Unlike the
``ckan_nacional`` reference connector (which wraps an official JSON API and is Tier A),
the Boletin Oficial exposes **no official structured API**, so this module SCRAPES the
public HTML pages and grounds everything as :data:`SourceTier.B` -- every result carries
the ``"[scraped -- verificar contra fuente oficial]"`` citation flag automatically.

Design rules honored here (see connectors/CLAUDE.md), identical to ckan_nacional:

    * All HTTP goes through ``common.fetch`` -- never instantiate ``httpx`` directly.
      That preserves the project's zero-retention guarantee.
    * Every tool returns ``to_dict(ground(...))`` with ``SourceTier.B`` -- never raw
      upstream data.
    * Tools NEVER raise to the MCP boundary. Any failure (source unreachable, bad
      status, empty/JS-only HTML) is turned into a grounded, explained error or
      ``found: false`` result so Claude can reason about it.

KEY FINDING -- HTML vs JavaScript (verified against the live site, 2026-06)
==========================================================================
The most important fact about this source: the content of an INDIVIDUAL AVISO is
served in the **initial HTML**, NOT injected later by JavaScript. A real fetch of
``/detalleAviso/primera/339128/20260306`` returns ~255 KB of HTML in which:

    * ``#tituloDetalleAviso`` holds the aviso title, and
    * ``#cuerpoDetalleAviso`` holds the full legal body text (~200 KB of real text,
      hundreds of "ARTICULO" occurrences, the publication date, etc.).

So ``httpx`` (which does not execute JS) CAN read an aviso. The connector parses those
elements with ``selectolax``. When those elements are ABSENT -- which is exactly what a
non-existent aviso id produces (the site answers HTTP 200 with a smaller shell page) --
the connector reports ``found: false`` honestly instead of inventing content.

WHAT IS NOT VIABLE: SECTION LISTINGS
====================================
The per-section daily listing (e.g. all avisos of "primera" on a date) IS rendered
client-side: the listing page ships an empty container that is populated by an
XHR/JS call after load, so plain ``httpx`` sees no avisos in the HTML. Rather than
ship a tool that silently returns nothing, ``boletin_list_seccion`` is implemented as
an HONEST stub that explains the limitation and returns ``found: false`` -- see its
docstring. (A future version could call the underlying XHR endpoint or use Playwright;
that is out of scope here.)
"""

from __future__ import annotations

import re
from typing import Any, Optional

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

#: Base URL of the public Boletin Oficial site.
BORA_BASE = "https://www.boletinoficial.gob.ar"

#: Tier for this whole connector: an HTML scrape of a predictable official source.
TIER = SourceTier.B

#: Per-request timeout (seconds). Generous: aviso pages can be ~250 KB of HTML.
HTTP_TIMEOUT = 30.0

#: TTL for cacheable responses (avisos are immutable once published), in seconds.
#: 1 hour: a published aviso never changes, so caching is safe and cheap.
_CACHE_TTL = 3600.0

#: Process-local cache. Safe per common/cache.py (single event loop, no persistence).
_cache = TTLCache(default_ttl=_CACHE_TTL)

#: Sections the Boletin Oficial is divided into. Used to validate the ``seccion`` arg.
VALID_SECCIONES = ("primera", "segunda", "tercera")

#: CSS ids that carry an aviso's content in the initial HTML (verified live).
_TITULO_SEL = "#tituloDetalleAviso"
_CUERPO_SEL = "#cuerpoDetalleAviso"

#: Matches "Fecha de publicacion DD/MM/YYYY" (with or without the accent on "publicacion")
#: that appears near the foot of an aviso body. Used to surface the publication date.
_FECHA_PUB_RE = re.compile(
    r"Fecha de publicaci[oó]n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE
)

mcp = FastMCP("boletin-nacional")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _aviso_url(aviso_id: str, fecha: str, seccion: str) -> str:
    """Build the canonical detalleAviso URL (also used as the grounded ``source_url``).

    Shape (verified live), e.g. ``/detalleAviso/primera/339128/20260306``::

        <BASE>/detalleAviso/<seccion>/<aviso_id>/<YYYYMMDD>
    """
    return f"{BORA_BASE}/detalleAviso/{seccion}/{aviso_id}/{fecha}"


def _seccion_url(seccion: str, fecha: str) -> str:
    """Build the per-section daily listing URL (used as ``source_url``).

    Shape, e.g. ``/seccion/primera?fecha=06-03-2026`` -- the date is dd-mm-yyyy here.
    The page itself is JS-rendered (see module docstring), so this URL is only used for
    provenance, not for scraping a listing.
    """
    return f"{BORA_BASE}/seccion/{seccion}?fecha={fecha}"


def _error(
    message: str,
    source_url: str,
    *,
    detail: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a grounded error result (same envelope as a success, never raises).

    The payload is an ``{"error": ...}`` dict so Claude can tell a failure from real
    data while still seeing the provenance fields (tier, source_url, retrieved_at).
    """
    payload: dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    note = f"Boletin Oficial request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, source_url, notes=note))


def _clean_ws(text: str) -> str:
    """Collapse runs of whitespace into single spaces and strip the ends.

    The aviso body is laid out with lots of incidental newlines/tabs from the HTML; this
    yields a readable, single-spaced string without touching the words themselves.
    """
    return re.sub(r"\s+", " ", text).strip()


def _is_valid_yyyymmdd(fecha: str) -> bool:
    """Cheap shape check for the ``YYYYMMDD`` date the detalleAviso URL expects."""
    return bool(re.fullmatch(r"\d{8}", fecha or ""))


def _parse_aviso(html: str) -> Optional[dict[str, Any]]:
    """Parse an aviso's title/body out of the detalleAviso HTML.

    Returns ``None`` when the page does not contain an aviso (e.g. a non-existent id,
    where the site answers HTTP 200 with a shell page that lacks ``#tituloDetalleAviso``
    and ``#cuerpoDetalleAviso``). Otherwise returns a dict with the extracted fields.

    The body element also contains some inline ``<style>`` CSS at the top (table
    styling); we drop ``<style>``/``<script>`` nodes before reading the text so the
    returned ``texto`` is clean legal prose, not stylesheet noise.
    """
    tree = HTMLParser(html)
    titulo_node = tree.css_first(_TITULO_SEL)
    cuerpo_node = tree.css_first(_CUERPO_SEL)

    # Absence of BOTH content elements == this page carries no aviso (not-found shell).
    if titulo_node is None and cuerpo_node is None:
        return None

    titulo = _clean_ws(titulo_node.text(strip=True)) if titulo_node is not None else ""

    texto = ""
    if cuerpo_node is not None:
        # Strip stylesheet/script nodes so they don't pollute the body text.
        for junk in cuerpo_node.css("style, script"):
            junk.decompose()
        texto = _clean_ws(cuerpo_node.text())

    # Document <title> is a reliable, human-readable summary headline.
    title_tag = tree.css_first("title")
    page_title = _clean_ws(title_tag.text()) if title_tag is not None else ""

    # Publication date, if the body exposes the "Fecha de publicacion ..." footer.
    fecha_match = _FECHA_PUB_RE.search(html)
    fecha_publicacion = fecha_match.group(1) if fecha_match else None

    return {
        "titulo": titulo,
        "page_title": page_title,
        "fecha_publicacion": fecha_publicacion,
        "texto": texto,
        "texto_chars": len(texto),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def boletin_get_aviso(
    aviso_id: str, fecha: str, seccion: str = "primera"
) -> dict[str, Any]:
    """Fetch and parse a single aviso from the Boletin Oficial by id + date + section.

    This SCRAPES ``boletinoficial.gob.ar/detalleAviso/<seccion>/<aviso_id>/<fecha>``.
    Because it is a scrape (no official API), the result is Tier B and carries the
    ``"[scraped -- verificar contra fuente oficial]"`` citation flag.

    Verified against the live site: an aviso's title and FULL legal body text are
    present in the initial HTML (not JS-rendered), so this tool returns real extracted
    content -- ``data.texto`` is the aviso body, ``data.titulo`` its heading.

    If the id/date/section combination does not resolve to an aviso, the site answers
    HTTP 200 with a shell page that has no aviso content; this tool detects that and
    returns ``data.found = False`` with an explanation, rather than inventing text.

    Parameters
    ----------
    aviso_id:
        The numeric aviso id, e.g. ``"339128"`` (as a string).
    fecha:
        Publication date in ``YYYYMMDD`` form, e.g. ``"20260306"``.
    seccion:
        One of ``"primera"`` (legislation/official notices), ``"segunda"`` (companies)
        or ``"tercera"`` (procurement/edicts). Defaults to ``"primera"``.

    Returns
    -------
    dict
        Grounded Tier-B result. On success ``data`` is::

            {
                "found": True,
                "aviso_id": "339128",
                "seccion": "primera",
                "fecha": "20260306",
                "titulo": "...",                # aviso heading
                "page_title": "...",            # document <title>
                "fecha_publicacion": "06/03/2026" | None,
                "texto": "...",                 # full body text
                "texto_chars": <int>,
            }

        When the aviso is absent, ``data`` is ``{"found": False, ...}`` with a message.
        On a transport failure it is an ``{"error": ...}`` dict.
    """
    aviso_id = (aviso_id or "").strip()
    seccion = (seccion or "").strip().lower()
    fecha = (fecha or "").strip()

    # Validate inputs up front so we build a sane source_url and avoid useless requests.
    if not aviso_id:
        return _error(
            "missing aviso_id",
            _aviso_url("", fecha or "00000000", seccion or "primera"),
            detail="provide a numeric aviso id, e.g. '339128'",
        )
    if seccion not in VALID_SECCIONES:
        return _error(
            "invalid seccion",
            _aviso_url(aviso_id, fecha or "00000000", seccion or "primera"),
            detail=f"seccion must be one of {VALID_SECCIONES}",
        )
    if not _is_valid_yyyymmdd(fecha):
        return _error(
            "invalid fecha",
            _aviso_url(aviso_id, fecha or "00000000", seccion),
            detail="fecha must be in YYYYMMDD form, e.g. '20260306'",
        )

    source_url = _aviso_url(aviso_id, fecha, seccion)

    cache_key = ("aviso", seccion, aviso_id, fecha)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = await fetch(source_url, timeout=HTTP_TIMEOUT)
    except SourceUnavailableError as exc:
        return _error("source unavailable", source_url, detail=str(exc))
    except SourceResponseError as exc:
        return _error(
            f"upstream returned HTTP {exc.status_code}",
            source_url,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )

    parsed = _parse_aviso(response.text)

    if parsed is None:
        # HTTP 200 but no aviso content == the id/date/section did not resolve, OR the
        # page unexpectedly started rendering content via JS. Report honestly.
        out = to_dict(
            ground(
                {
                    "found": False,
                    "aviso_id": aviso_id,
                    "seccion": seccion,
                    "fecha": fecha,
                    "message": (
                        "No aviso content was found at this URL. The page loaded "
                        "(HTTP 200) but contained neither the title nor body element "
                        "of an aviso, which is what the site returns for a "
                        "non-existent id/date/section combination. Verify the id, "
                        "date (YYYYMMDD) and section against the official site."
                    ),
                },
                TIER,
                source_url,
                notes=(
                    "Scraped detalleAviso page contained no aviso content "
                    "(#tituloDetalleAviso / #cuerpoDetalleAviso absent)."
                ),
            )
        )
        # Do NOT cache a not-found: an id may become valid as data is published.
        return out

    # Defensive: a parsed page with an empty body would mean the site changed to JS
    # rendering. Surface that honestly rather than returning blank "extracted" text.
    if not parsed.get("texto"):
        return to_dict(
            ground(
                {
                    "found": True,
                    "aviso_id": aviso_id,
                    "seccion": seccion,
                    "fecha": fecha,
                    "titulo": parsed.get("titulo", ""),
                    "page_title": parsed.get("page_title", ""),
                    "texto": "",
                    "texto_chars": 0,
                    "message": (
                        "The aviso page was found but its body text could not be "
                        "extracted from the static HTML. This can happen if the site "
                        "moved to client-side (JavaScript) rendering of the body, "
                        "which a plain HTTP fetch cannot see. Verify directly on the "
                        "official site."
                    ),
                },
                TIER,
                source_url,
                notes=(
                    "Title found but body text empty -- possible JS-rendered body; "
                    "reported honestly, not fabricated."
                ),
            )
        )

    data = {
        "found": True,
        "aviso_id": aviso_id,
        "seccion": seccion,
        "fecha": fecha,
        "titulo": parsed["titulo"],
        "page_title": parsed["page_title"],
        "fecha_publicacion": parsed["fecha_publicacion"],
        "texto": parsed["texto"],
        "texto_chars": parsed["texto_chars"],
    }
    out = to_dict(
        ground(
            data,
            TIER,
            source_url,
            notes=(
                "Scraped from the initial HTML of the detalleAviso page (title + body "
                "are NOT JavaScript-rendered, so httpx can read them directly)."
            ),
        )
    )
    _cache.set(cache_key, out)
    return out


@mcp.tool
async def boletin_list_seccion(seccion: str, fecha: str) -> dict[str, Any]:
    """List the avisos of one section on a given date -- NOT VIABLE via static scraping.

    HONESTY NOTE: this tool is intentionally a documented stub. The per-section daily
    listing page (``/seccion/<seccion>?fecha=dd-mm-yyyy``) populates its list of avisos
    CLIENT-SIDE via JavaScript/XHR AFTER the page loads. A plain HTTP fetch (which does
    not execute JavaScript) therefore sees an empty container and no avisos. Rather than
    return a misleading empty or fabricated list, this tool reports the limitation.

    To read an individual aviso you already know the id/date of, use
    ``boletin_get_aviso`` -- that content IS in the static HTML and works reliably.

    Parameters
    ----------
    seccion:
        One of ``"primera"``, ``"segunda"``, ``"tercera"``.
    fecha:
        Date in ``YYYYMMDD`` form, e.g. ``"20260306"``.

    Returns
    -------
    dict
        Grounded Tier-B result whose ``data`` explains that listing is not available
        via static scraping (``data.found = False``, ``data.avisos = []``).
    """
    seccion = (seccion or "").strip().lower()
    fecha = (fecha or "").strip()

    # Build a human-meaningful source_url (dd-mm-yyyy) for provenance even though we do
    # not actually scrape a listing from it.
    if _is_valid_yyyymmdd(fecha):
        fecha_url = f"{fecha[6:8]}-{fecha[4:6]}-{fecha[0:4]}"
    else:
        fecha_url = fecha or "00-00-0000"
    source_url = _seccion_url(seccion or "primera", fecha_url)

    if seccion not in VALID_SECCIONES:
        return _error(
            "invalid seccion",
            source_url,
            detail=f"seccion must be one of {VALID_SECCIONES}",
        )
    if not _is_valid_yyyymmdd(fecha):
        return _error(
            "invalid fecha",
            source_url,
            detail="fecha must be in YYYYMMDD form, e.g. '20260306'",
        )

    return to_dict(
        ground(
            {
                "found": False,
                "seccion": seccion,
                "fecha": fecha,
                "avisos": [],
                "message": (
                    "Section listings cannot be scraped: the Boletin Oficial renders "
                    "the per-section list of avisos client-side (JavaScript/XHR), so a "
                    "plain HTTP fetch sees no avisos. A headless browser (e.g. "
                    "Playwright) or the site's underlying XHR endpoint would be needed; "
                    "that is out of scope for this connector. To read a specific aviso "
                    "whose id and date you know, use boletin_get_aviso instead."
                ),
            },
            TIER,
            source_url,
            notes=(
                "Listing not implemented: section pages are JavaScript-rendered and "
                "not readable from static HTML. Reported honestly rather than returning "
                "an empty/fabricated list."
            ),
        )
    )


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
