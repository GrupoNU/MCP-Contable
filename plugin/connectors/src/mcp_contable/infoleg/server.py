"""FastMCP server for InfoLEG (servicios.infoleg.gob.ar) -- national legislation (Tier B).

InfoLEG is Argentina's national legislative-information database (Ministry of Justice).
There is NO official structured API: this connector SCRAPES the public HTML pages, so it
is a Tier B source. Every result carries the verification flag
``[scraped -- verificar contra fuente oficial]`` automatically (see common/grounding.py),
because the page structure can change and the backend is occasionally flaky.

Design rules honored here (see connectors/CLAUDE.md):

    * All HTTP goes through ``common.fetch`` -- never instantiate ``httpx`` directly.
    * Every tool returns ``to_dict(ground(...))`` with ``SourceTier.B`` -- never raw HTML.
    * Tools NEVER raise to the MCP boundary. Any failure (source unreachable, bad status,
      empty/unexpected HTML) becomes a grounded, explained error dict (same ``_error``
      envelope as the ckan_nacional reference connector).

WHAT WE CAN ACTUALLY EXTRACT (verified live against verNorma.do?id=423722 = Ley 27801)
=====================================================================================
The norma detail page (``verNorma.do?id=<ID>``) has a stable, server-rendered block
``<div id="Textos_Completos">`` from which we reliably parse:

    * tipo + numero      -- the leading ``<strong>`` (e.g. "Ley 27801 HONORABLE CONGRESO...")
    * fecha_sancion      -- ``<span class="vr_azul11">`` (e.g. "27-feb-2026")
    * materia / titulo   -- ``<span class="destacado">`` (e.g. "REGIMEN PENAL JUVENIL")
    * disposicion        -- the ``<h1>`` (e.g. "DISPOSICIONES")
    * boletin_oficial    -- publication date + BO number from the "Publicada en el
                            Boletin Oficial" paragraph
    * resumen            -- the paragraph after ``<strong>Resumen:</strong>``
    * texto_completo_url -- the "Texto completo de la norma" anchor (relative -> absolutized)

Fields are emitted only when present; nothing is invented. See ``infoleg_get_norma``.

WHY THERE IS NO REAL SEARCH (honest limitation)
===============================================
The public search UI (``mostrarBusquedaNormas.do`` / ``buscarNormas.do``) is an
iframe-embedded JSP form whose backend was observed returning 502/503/timeout
repeatedly during development -- it is too fragile/JS-dependent to scrape reliably.
``infoleg_search_norma`` therefore does NOT fabricate results: it returns an explained
result telling the caller to use ``infoleg_get_norma`` with a known numeric ID, plus the
public search URL a human can use in a browser. See its docstring.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from fastmcp import FastMCP

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

#: Base host for the InfoLEG internet application.
INFOLEG_BASE = "https://servicios.infoleg.gob.ar/infolegInternet"

#: Detail page for a single norma, parameterized by numeric id.
VER_NORMA_URL = f"{INFOLEG_BASE}/verNorma.do"

#: Public, human-usable search page (an iframe-embedded JSP form, not scrapeable here).
BUSQUEDA_URL = f"{INFOLEG_BASE}/mostrarBusquedaNormas.do"

#: Tier for this whole connector: HTML scraping of an official source => Tier B.
TIER = SourceTier.B

#: Per-request timeout (seconds). Generous: the InfoLEG JSP backend is slow and flaky.
HTTP_TIMEOUT = 45.0

#: TTL for a parsed norma. Legislation text is immutable once published, so cache long.
_CACHE_TTL = 3600.0

#: Process-local cache. Safe per common/cache.py (single event loop, no persistence).
_cache = TTLCache(default_ttl=_CACHE_TTL)

mcp = FastMCP("infoleg")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _norma_url(norma_id: str) -> str:
    """Build the public verNorma.do URL for a numeric id (used as ``source_url``)."""
    return f"{VER_NORMA_URL}?id={norma_id}"


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
    note = f"InfoLEG request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, source_url, notes=note))


def _clean(text: Optional[str]) -> str:
    """Collapse runs of whitespace (incl. the page's heavy tab/newline indentation)."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _first_text(tree: HTMLParser, selector: str) -> str:
    """Return cleaned text of the first node matching ``selector``, or ""."""
    node = tree.css_first(selector)
    if node is None:
        return ""
    return _clean(node.text())


def _parse_tipo_numero(strong_text: str) -> dict[str, Any]:
    """Split the leading <strong> into tipo / numero / organismo when possible.

    Example input (already whitespace-collapsed):
        "Ley 27801 HONORABLE CONGRESO DE LA NACION ARGENTINA"

    Returns a dict with whatever could be parsed: always ``raw``; plus ``tipo``,
    ``numero`` and ``organismo`` when the regex matches. Nothing is invented -- if the
    pattern does not match, only ``raw`` is returned.
    """
    raw = _clean(strong_text)
    out: dict[str, Any] = {}
    # tipo = leading word(s) of letters; numero = the following integer; the remainder
    # (if any) is the issuing body. The number may be absent for some norma types.
    m = re.match(r"^([A-Za-zÁÉÍÓÚÑáéíóúñ.\s]+?)\s+(\d[\d.]*)\b\s*(.*)$", raw)
    if m:
        out["tipo"] = _clean(m.group(1))
        out["numero"] = m.group(2).replace(".", "")
        organismo = _clean(m.group(3))
        if organismo:
            out["organismo"] = organismo
    return out


def _parse_boletin(p_text: str) -> dict[str, Any]:
    """Extract BO publication date and number from the 'Publicada en el Boletin...' <p>.

    The cleaned paragraph looks like:
        "Publicada en el Boletin Oficial del 09-mar-2026 Numero: 35866 Pagina: 4"
    Returns only the keys it can find (fecha / numero / pagina).
    """
    out: dict[str, Any] = {}
    txt = _clean(p_text)
    m_fecha = re.search(r"del\s+(\d{1,2}-[a-zA-Z]{3}-\d{4})", txt)
    if m_fecha:
        out["fecha"] = m_fecha.group(1)
    m_num = re.search(r"N[uú]mero:\s*(\d+)", txt)
    if m_num:
        out["numero"] = m_num.group(1)
    m_pag = re.search(r"P[aá]gina:\s*(\d+)", txt)
    if m_pag:
        out["pagina"] = m_pag.group(1)
    return out


def _parse_resumen(tree: HTMLParser) -> str:
    """Return the 'Resumen:' paragraph text (without the bold label), or "".

    The page structure is ``<p><strong>Resumen:</strong><br/> <text> </p>``. We locate
    the <p> whose <strong> says 'Resumen', then strip the label from its full text.
    """
    for p in tree.css("#Textos_Completos p"):
        strong = p.css_first("strong")
        if strong and "resumen" in _clean(strong.text()).lower():
            full = _clean(p.text())
            # Drop the leading "Resumen:" label (with or without trailing colon).
            return re.sub(r"^Resumen:?\s*", "", full, flags=re.IGNORECASE).strip()
    return ""


def _parse_norma_html(html: str, source_url: str) -> Optional[dict[str, Any]]:
    """Parse a verNorma.do page into a structured dict, or None if it is not a norma.

    Returns None when the expected ``#Textos_Completos`` block is absent (e.g. an error
    page, an empty/unknown id, or a backend error page) so the caller can report a
    graceful "no norma found" result instead of emitting empty fields.
    """
    tree = HTMLParser(html)
    block = tree.css_first("#Textos_Completos")
    if block is None:
        return None

    data: dict[str, Any] = {}

    # tipo + numero + organismo from the leading <strong>.
    strong = block.css_first("p strong")
    if strong is not None:
        data.update(_parse_tipo_numero(strong.text()))

    # fecha de sancion: <span class="vr_azul11">
    fecha = _first_text(block, "span.vr_azul11")
    if fecha:
        data["fecha_sancion"] = fecha

    # materia / subject: <span class="destacado">
    materia = _first_text(block, "span.destacado")
    if materia:
        data["materia"] = materia

    # disposicion heading: <h1>
    disposicion = _first_text(block, "h1")
    if disposicion:
        data["disposicion"] = disposicion

    # Boletin Oficial publication info: the <p> containing "Publicada en el Bolet".
    for p in block.css("p"):
        ptxt = _clean(p.text())
        if "publicada en el bolet" in ptxt.lower():
            bo = _parse_boletin(ptxt)
            if bo:
                data["boletin_oficial"] = bo
            break

    # Resumen.
    resumen = _parse_resumen(tree)
    if resumen:
        data["resumen"] = resumen

    # Link to the full text of the norma ("Texto completo de la norma").
    for a in block.css("a"):
        if "texto completo" in _clean(a.text()).lower():
            href = a.attributes.get("href")
            if href:
                data["texto_completo_url"] = urljoin(source_url, href)
            break

    return data


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def infoleg_get_norma(norma_id: str) -> dict[str, Any]:
    """Fetch and parse a single InfoLEG norma by its numeric InfoLEG id.

    Scrapes ``verNorma.do?id=<norma_id>`` (Tier B). The ``norma_id`` is InfoLEG's own
    numeric identifier for the norma -- NOT the law number. For example, id ``423722``
    is *Ley 27801*. You typically obtain such ids from datos.jus.gob.ar (the CKAN
    ``base-de-datos-legislativos-infoleg`` dataset) or from an InfoLEG URL.

    Returns ONLY the fields actually present in the page (nothing is invented). When the
    page parses successfully, ``data`` may include:

        * ``tipo``               -- norma type, e.g. "Ley", "Decreto", "Resolucion"
        * ``numero``             -- norma number, e.g. "27801"
        * ``organismo``          -- issuing body, when stated in the header
        * ``fecha_sancion``      -- sanction date as printed, e.g. "27-feb-2026"
        * ``materia``            -- subject/heading, e.g. "REGIMEN PENAL JUVENIL"
        * ``disposicion``        -- the disposition heading, e.g. "DISPOSICIONES"
        * ``boletin_oficial``    -- {fecha, numero, pagina} of the Boletin Oficial pub.
        * ``resumen``            -- the official summary paragraph
        * ``texto_completo_url`` -- absolute URL of the full norma text (an HTML file)
        * ``source_url``         -- ALWAYS present: the verNorma.do URL scraped

    Graceful behavior (never raises): an unreachable/erroring backend, or a page with no
    recognizable norma block (bad/unknown id), yields an ``{"error": ...}`` payload that
    still carries provenance. InfoLEG's backend is occasionally flaky (502/503); the
    shared HTTP layer retries transient 5xx automatically.

    Parameters
    ----------
    norma_id:
        InfoLEG's numeric id of the norma (digits only), e.g. ``"423722"``.

    Returns
    -------
    dict
        Grounded result (``source_tier="B"``,
        ``citation_flag="[scraped -- verificar contra fuente oficial]"``).
    """
    norma_id = (norma_id or "").strip()
    if not norma_id:
        return _error(
            "missing norma_id",
            VER_NORMA_URL,
            detail="provide InfoLEG's numeric id, e.g. 423722 for Ley 27801",
        )
    if not norma_id.isdigit():
        return _error(
            "invalid norma_id",
            _norma_url(norma_id),
            detail="norma_id must be numeric (InfoLEG's internal id), e.g. 423722",
        )

    source_url = _norma_url(norma_id)

    cache_key = ("norma", norma_id)
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

    # InfoLEG serves ISO-8859-1. httpx usually detects this from the meta charset, but
    # fall back explicitly so accented text is decoded correctly regardless.
    if not response.encoding:
        response.encoding = "iso-8859-1"
    html = response.text

    parsed = _parse_norma_html(html, source_url)
    if not parsed:
        return _error(
            "no norma found at this id",
            source_url,
            detail=(
                "the page did not contain a recognizable norma block; the id may be "
                "unknown, or InfoLEG returned an error/empty page"
            ),
        )

    out = to_dict(
        ground(
            parsed,
            TIER,
            source_url,
            notes=(
                "Scraped from InfoLEG verNorma.do (Tier B). Fields present only when "
                "found in the page; full text lives at 'texto_completo_url'."
            ),
        )
    )
    _cache.set(cache_key, out)
    return out


@mcp.tool
async def infoleg_search_norma(
    tipo: str = "", numero: str = "", anio: str = "", texto: str = ""
) -> dict[str, Any]:
    """Search guidance for InfoLEG normas (NOTE: programmatic search is NOT available).

    HONEST LIMITATION -- READ THIS. InfoLEG exposes NO official search API. Its public
    search UI (``mostrarBusquedaNormas.do`` / ``buscarNormas.do``) is an iframe-embedded
    JSP form whose backend was observed returning 502/503/timeout repeatedly and is too
    fragile/JS-dependent to scrape reliably. This tool therefore does NOT return scraped
    search hits -- doing so would risk fabricating or silently dropping results.

    Instead it returns an explained, grounded result that:

        * echoes back your query parameters,
        * gives the public, human-usable search URL (open it in a browser), and
        * tells you to call ``infoleg_get_norma`` once you have a numeric InfoLEG id
          (for instance from the datos.jus.gob.ar CKAN dataset
          ``base-de-datos-legislativos-infoleg``, served by the ckan_nacional connector).

    No HTTP request is made here (the search backend is unreliable), so this tool is
    fast and never fails.

    Parameters
    ----------
    tipo:
        Norma type filter you intend to search for, e.g. "Ley", "Decreto" (informational).
    numero:
        Norma number you are looking for (informational).
    anio:
        Year filter (informational).
    texto:
        Free-text terms (informational).

    Returns
    -------
    dict
        Grounded result (``source_tier="B"``) whose ``data`` carries
        ``search_available: false``, the echoed ``query``, a ``search_url`` to use
        manually, and guidance pointing at ``infoleg_get_norma``.
    """
    query = {
        "tipo": (tipo or "").strip(),
        "numero": (numero or "").strip(),
        "anio": (anio or "").strip(),
        "texto": (texto or "").strip(),
    }
    data = {
        "search_available": False,
        "query": query,
        "search_url": BUSQUEDA_URL,
        "guidance": (
            "InfoLEG has no reliable programmatic search (its search backend is an "
            "iframe JSP form that frequently returns 502/503). To retrieve a norma "
            "with this connector, obtain its NUMERIC InfoLEG id and call "
            "infoleg_get_norma(norma_id). InfoLEG ids are available in the "
            "datos.jus.gob.ar CKAN dataset 'base-de-datos-legislativos-infoleg' "
            "(use the ckan_nacional connector), or from an InfoLEG verNorma.do URL. "
            "Example: norma_id 423722 -> Ley 27801."
        ),
    }
    return to_dict(
        ground(
            data,
            TIER,
            BUSQUEDA_URL,
            notes=(
                "No programmatic InfoLEG search: returning manual-search guidance "
                "instead of fabricated results. Use infoleg_get_norma with a known id."
            ),
        )
    )


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
