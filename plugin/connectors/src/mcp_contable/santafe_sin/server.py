"""FastMCP server for the Santa Fe SIN (www.santafe.gov.ar/normativa) -- provincial
legislation (Tier B).

The SIN (*Sistema de Informacion de Normativa*) is the Province of Santa Fe's public
normativa database (Leyes, Decretos, Disposiciones, Resoluciones, Dictamenes). In
MCP-Contable it is used for **provincial fiscal normativa**: the Codigo Fiscal (Ley 3456),
Ingresos Brutos resolutions and the Resoluciones Generales of the provincial tax authority
(API - Administracion Provincial de Impuestos). There is NO official structured API: this
connector SCRAPES the public HTML, so it is a Tier B source. Every result carries the
verification flag ``[scraped -- verificar contra fuente oficial]`` automatically (see
common/grounding.py), because the page structure can change.

Design rules honored here (see connectors/CLAUDE.md):

    * All HTTP goes through ``common.fetch`` -- never instantiate ``httpx`` directly.
    * Every tool returns ``to_dict(ground(...))`` with ``SourceTier.B`` -- never raw HTML.
    * Tools NEVER raise to the MCP boundary. Any failure (source unreachable, bad status,
      empty/unexpected HTML) becomes a grounded, explained error dict (same ``_error``
      envelope as the infoleg reference connector).

HOW THE SEARCH ACTUALLY WORKS (verified live against www.santafe.gov.ar/normativa)
=================================================================================
The home page (``/normativa/``) embeds ``<form id="form_buscar" method="post">``. The
form is submitted by JavaScript via AJAX (``$(this).serialize()``) to:

    POST /normativa/src/busqueda.php?organismo=&tbusqueda=

There is NO viewstate, NO CSRF token and NO session/cookie requirement -- the endpoint is
a plain stateless POST. We replicate that request directly with ``common.fetch`` (POST +
form params). The endpoint returns an HTML FRAGMENT (the ``#bloqueResultados`` table) that
the page injects into ``#results``. We parse that fragment.

IMPORTANT QUIRK (verified): the ``tema[]`` form field MUST NOT be sent empty -- including
``tema[]=`` makes ``busqueda.php`` return HTTP 400 with an empty body. We therefore omit it
entirely (we never filter by tema), and the search returns 200 normally.

WHAT WE EXTRACT FROM A SEARCH RESULT ROW (verified live)
========================================================
Each result is a ``<tbody><tr>`` with five ``<td>``:

    td[0] numero        -- e.g. "13000"
    td[1] tipo          -- e.g. "LEY", "DECRETO"
    td[2] descripcion   -- the full free-text description / sumario
    td[3] fecha         -- e.g. "10-09-2009"
    td[4] <a href="item.php?id=<ID>&cod=<HASH>">Ver</a>  -- the detail link

We also read the "La consulta ha arrojado N resultados" banner to report the total count
(the listing is paginated at 10 rows/page; ``pagina`` selects the page).

WHAT WE EXTRACT FROM A NORMA DETAIL PAGE (item.php, verified live)
=================================================================
``item.php?id=<ID>&cod=<HASH>`` is a full page whose ``<div class="row form detalles">``
holds the norma. Inside, fields are ``<label>Name:</label><span>value</span>`` pairs and a
"Texto completo" table with downloadable files. We reliably parse:

    * tipo + numero    -- from the ``<h3>`` heading (e.g. "LEY  13000")
    * a generic ``campos`` map from every label/span pair (numero, fecha, firmantes,
      temas, descripcion, jurisdiccion, etc. -- whatever the page lists)
    * archivos          -- list of {nombre, descripcion, tamanio, url} from the texto-
                          completo table (the actual PDF/file download links)
    * source_url        -- the item.php URL scraped

Nothing is invented: a field is emitted only when present in the page. The detail link's
``cod`` hash is REQUIRED (``item.php`` without it does not render the norma), so
``santafe_sin_get_norma`` accepts the full relative/absolute item.php URL (or the
``id``+``cod`` query) rather than a bare numeric id.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import parse_qs, urljoin, urlsplit

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

#: Base of the SIN web application (note the trailing slash mirrors <base href>).
SIN_BASE = "https://www.santafe.gov.ar/normativa/"

#: Public home page (the human-usable search UI).
SIN_HOME_URL = SIN_BASE

#: AJAX search endpoint the form POSTs to (no token/session required; verified live).
SIN_SEARCH_URL = f"{SIN_BASE}src/busqueda.php?organismo=&tbusqueda="

#: Detail page for a single norma (needs both id and cod query params).
SIN_ITEM_URL = f"{SIN_BASE}item.php"

#: Tier for this whole connector: HTML scraping of an official source => Tier B.
TIER = SourceTier.B

#: Per-request timeout (seconds). The text-search endpoint can be slow on wide queries.
HTTP_TIMEOUT = 60.0

#: TTL for parsed results. Provincial legislation is effectively immutable once
#: published, so cache generously.
_CACHE_TTL = 3600.0

#: Process-local cache. Safe per common/cache.py (single event loop, no persistence).
_cache = TTLCache(default_ttl=_CACHE_TTL)

#: Map a human ``tipo`` string to the SIN ``tipoNorma`` select value (verified live).
#: Note there is no value "3" in the SIN form. Keys are matched case-insensitively and
#: tolerate singular/plural ("ley"/"leyes", "decreto"/"decretos", ...).
TIPO_NORMA_MAP: dict[str, str] = {
    "ley": "1",
    "leyes": "1",
    "decreto": "2",
    "decretos": "2",
    "disposicion": "4",
    "disposiciones": "4",
    "resolucion": "5",
    "resoluciones": "5",
    "dictamen": "6",
    "dictamenes": "6",
}

mcp = FastMCP("santafe_sin")


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
    """Build a grounded error result (same envelope as a success, never raises).

    The payload is an ``{"error": ...}`` dict so Claude can tell a failure from real
    data while still seeing the provenance fields (tier, source_url, retrieved_at).
    """
    payload: dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    note = f"Santa Fe SIN request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, source_url, notes=note))


def _clean(text: Optional[str]) -> str:
    """Collapse runs of whitespace (incl. the page's heavy tab/newline indentation)."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _normalize_tipo(tipo: str) -> str:
    """Strip accents and lowercase a tipo string for tolerant map lookups."""
    t = _clean(tipo).lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        t = t.replace(a, b)
    return t


def _label_key(label_text: str) -> str:
    """Turn a ``<label>`` text ("Numero: ") into a snake_case dict key ("numero")."""
    key = _clean(label_text).rstrip(":").strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        key = key.replace(a, b)
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return key


def _parse_results_html(html: str) -> dict[str, Any]:
    """Parse the busqueda.php fragment into ``{total, count, results: [...]}``.

    Each result carries: ``numero``, ``tipo``, ``descripcion``, ``fecha`` and
    ``item_url`` (absolute) plus ``id``/``cod`` when extractable. Fields are emitted
    only when present. The reported ``total`` comes from the "arrojado N" banner.
    """
    tree = HTMLParser(html)

    results: list[dict[str, Any]] = []
    for tr in tree.css("#bloqueResultados tbody tr"):
        tds = tr.css("td")
        if len(tds) < 4:
            continue
        row: dict[str, Any] = {}
        numero = _clean(tds[0].text())
        tipo = _clean(tds[1].text())
        descripcion = _clean(tds[2].text())
        fecha = _clean(tds[3].text())
        if numero:
            row["numero"] = numero
        if tipo:
            row["tipo"] = tipo
        if descripcion:
            row["descripcion"] = descripcion
        if fecha:
            row["fecha"] = fecha

        anchor = tr.css_first("a[href]")
        if anchor is not None:
            href = anchor.attributes.get("href")
            if href:
                # The result links are relative to the page's <base href="/normativa/">
                # (NOT to busqueda.php, which lives under /normativa/src/), so resolve
                # against SIN_BASE to get the correct /normativa/item.php URL.
                item_url = urljoin(SIN_BASE, href)
                row["item_url"] = item_url
                qs = parse_qs(urlsplit(item_url).query)
                if qs.get("id"):
                    row["id"] = qs["id"][0]
                if qs.get("cod"):
                    row["cod"] = qs["cod"][0]
        if row:
            results.append(row)

    out: dict[str, Any] = {"count": len(results), "results": results}

    # "La consulta ha arrojado N resultado(s)." -> total across all pages.
    m_total = re.search(r"arrojado\s+(\d+)\s+resultado", html, flags=re.IGNORECASE)
    if m_total:
        out["total"] = int(m_total.group(1))

    return out


def _parse_item_html(html: str, source_url: str) -> Optional[dict[str, Any]]:
    """Parse an item.php detail page into a structured dict, or None if not a norma.

    Returns None when the expected ``div.row.form.detalles`` block is absent (e.g. the
    ``cod`` hash was missing/invalid, or an error page) so the caller can report a
    graceful "no norma found" result instead of emitting empty fields.
    """
    tree = HTMLParser(html)
    block = tree.css_first("div.row.form.detalles")
    if block is None:
        return None

    data: dict[str, Any] = {}

    # tipo + numero from the <h3> heading, e.g. "LEY  13000".
    h3 = block.css_first("h3")
    if h3 is not None:
        heading = _clean(h3.text())
        if heading:
            data["titulo"] = heading
            m = re.match(r"^([A-Za-zÁÉÍÓÚÑáéíóúñ.\s]+?)\s+(\d[\d./]*)\s*$", heading)
            if m:
                data["tipo"] = _clean(m.group(1))
                data["numero"] = m.group(2)

    # Generic label/span field map. Every detail field on the page follows the shape
    # <div class="...col..."><label>Name: </label><span>value</span></div>.
    campos: dict[str, Any] = {}
    for div in block.css("div[class*='col']"):
        label = div.css_first("label")
        span = div.css_first("span")
        if label is None or span is None:
            continue
        key = _label_key(label.text())
        value = _clean(span.text())
        if key and value:
            campos[key] = value
    if campos:
        data["campos"] = campos
        # Surface the most useful fields at the top level too (when present).
        for top in ("numero", "fecha", "descripcion"):
            if top in campos and top not in data:
                data[top] = campos[top]

    # Texto completo: downloadable files table (the actual norma text PDFs).
    archivos: list[dict[str, Any]] = []
    for tr in block.css("table tbody tr"):
        tds = tr.css("td")
        if len(tds) < 1:
            continue
        archivo: dict[str, Any] = {}
        nombre = _clean(tds[0].text()) if len(tds) >= 1 else ""
        descripcion = _clean(tds[1].text()) if len(tds) >= 2 else ""
        tamanio = _clean(tds[2].text()) if len(tds) >= 3 else ""
        if nombre:
            archivo["nombre"] = nombre
        if descripcion:
            archivo["descripcion"] = descripcion
        if tamanio:
            archivo["tamanio"] = tamanio
        anchor = tr.css_first("a[href]")
        if anchor is not None:
            href = anchor.attributes.get("href")
            if href:
                archivo["url"] = urljoin(source_url, href)
        if archivo:
            archivos.append(archivo)
    if archivos:
        data["archivos"] = archivos

    return data


def _build_item_url(norma_url_or_id: str) -> Optional[str]:
    """Resolve the user-supplied identifier into an absolute item.php URL.

    Accepts, in order of preference:
      * a full absolute URL (``https://www.santafe.gov.ar/normativa/item.php?id=..&cod=..``)
      * a relative item.php query (``item.php?id=..&cod=..``)
      * a bare ``id=..&cod=..`` query string
    Returns None if no ``cod`` could be found (item.php requires it to render the norma).
    """
    raw = (norma_url_or_id or "").strip()
    if not raw:
        return None

    # Absolute or relative URL containing item.php -> absolutize and validate it has cod.
    if "item.php" in raw or raw.startswith("http"):
        absolute = urljoin(SIN_BASE, raw)
        qs = parse_qs(urlsplit(absolute).query)
        if qs.get("id") and qs.get("cod"):
            return f"{SIN_ITEM_URL}?id={qs['id'][0]}&cod={qs['cod'][0]}"
        return None

    # A bare query string like "id=109468&cod=abc...".
    qs = parse_qs(raw.lstrip("?"))
    if qs.get("id") and qs.get("cod"):
        return f"{SIN_ITEM_URL}?id={qs['id'][0]}&cod={qs['cod'][0]}"
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def santafe_sin_buscar(
    tipo: str = "", numero: str = "", anio: str = "", texto: str = ""
) -> dict[str, Any]:
    """Search the Santa Fe SIN provincial-normativa database (Tier B HTML scraper).

    Replicates the SIN's own AJAX search (POST to ``src/busqueda.php``) -- a plain,
    stateless POST with no token or session -- and parses the returned results table.
    The search IS functional and reasonably reliable (verified live), but remember it is
    a scraper: every result carries the Tier B verification flag.

    Provide at least one meaningful filter (``tipo``, ``numero``, ``anio`` or ``texto``);
    an all-empty query is rejected to avoid scraping the whole database.

    Parameters
    ----------
    tipo:
        Norma type. Accepted (case-insensitive, singular or plural): "Ley"/"Leyes",
        "Decreto"/"Decretos", "Disposicion"/"Disposiciones", "Resolucion"/"Resoluciones",
        "Dictamen"/"Dictamenes". The SIN REQUIRES a tipo for a search, so if you omit it
        this tool defaults to "Ley" and says so in ``notes``.
    numero:
        Norma number, WITHOUT leading zeros (e.g. "13000"). Optional.
    anio:
        Year (e.g. "2020"). Optional.
    texto:
        Free-text terms searched in the norma description ("any word" mode). Optional.

    Returns
    -------
    dict
        Grounded result (``source_tier="B"``). ``data`` carries:
          * ``query``      -- the echoed/normalized filters actually sent
          * ``total``      -- total matches reported by the SIN (across all pages)
          * ``count``      -- number of rows on this page (max 10)
          * ``results``    -- list of {numero, tipo, descripcion, fecha, item_url, id, cod}
        On no matches, ``results`` is empty and ``total`` is 0 (graceful, not an error).
        Pass a result's ``item_url`` to ``santafe_sin_get_norma`` for the full detail.
    """
    tipo_raw = (tipo or "").strip()
    numero = (numero or "").strip()
    anio = (anio or "").strip()
    texto = (texto or "").strip()

    if not any((tipo_raw, numero, anio, texto)):
        return _error(
            "empty query",
            SIN_SEARCH_URL,
            detail="provide at least one of: tipo, numero, anio, texto",
        )

    # Resolve tipo -> SIN tipoNorma value. The SIN requires a tipo; default to Ley.
    tipo_defaulted = False
    if tipo_raw:
        tipo_norma = TIPO_NORMA_MAP.get(_normalize_tipo(tipo_raw))
        if tipo_norma is None:
            return _error(
                "unknown tipo",
                SIN_SEARCH_URL,
                detail=(
                    "tipo must be one of: Ley, Decreto, Disposicion, Resolucion, "
                    f"Dictamen (got {tipo_raw!r})"
                ),
            )
    else:
        tipo_norma = "1"  # Ley
        tipo_defaulted = True

    # NOTE: 'tema[]' is deliberately omitted -- sending it empty makes busqueda.php 400.
    form: dict[str, str] = {
        "numNorma": numero,
        "anio": anio,
        "numExpediente": "",
        "fechaDesde": "",
        "fechaHasta": "",
        "action": "buscar",
        "pagina": "1",
        "ordenarPor": "2",
        "ordenBusqueda": "ASC",
        "tipoNorma": tipo_norma,
        "organismoSelect": "",
        "frase": "alguna",
        "iniciador": "",
        "textoNorma": texto,
        "boton": "",
    }

    cache_key = ("buscar", tipo_norma, numero, anio, texto)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = await fetch(
            SIN_SEARCH_URL,
            method="POST",
            params=form,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": SIN_HOME_URL,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=HTTP_TIMEOUT,
        )
    except SourceUnavailableError as exc:
        return _error("source unavailable", SIN_SEARCH_URL, detail=str(exc))
    except SourceResponseError as exc:
        return _error(
            f"upstream returned HTTP {exc.status_code}",
            SIN_SEARCH_URL,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )

    # busqueda.php serves UTF-8.
    if not response.encoding:
        response.encoding = "utf-8"
    html = response.text

    data = _parse_results_html(html)
    data["query"] = {
        "tipo": tipo_raw or "Ley (default)",
        "numero": numero,
        "anio": anio,
        "texto": texto,
    }

    note = (
        "Scraped from Santa Fe SIN busqueda.php (Tier B). Pass a result's 'item_url' "
        "to santafe_sin_get_norma for the full detail. Listing is paginated at 10/page; "
        "'total' is the full match count."
    )
    if tipo_defaulted:
        note = "No 'tipo' given; defaulted to 'Ley' (the SIN requires one). " + note

    out = to_dict(ground(data, TIER, SIN_SEARCH_URL, notes=note))
    _cache.set(cache_key, out)
    return out


@mcp.tool
async def santafe_sin_get_norma(norma_url_or_id: str) -> dict[str, Any]:
    """Fetch and parse a single Santa Fe SIN norma detail page (Tier B HTML scraper).

    Scrapes ``item.php?id=<ID>&cod=<HASH>``. The SIN's detail page REQUIRES both the
    numeric ``id`` and its ``cod`` hash (item.php without the cod does not render the
    norma), so a bare numeric id is NOT enough. Pass one of:

        * the full ``item_url`` returned by ``santafe_sin_buscar`` (recommended), e.g.
          "https://www.santafe.gov.ar/normativa/item.php?id=109468&cod=b4d8...",
        * a relative "item.php?id=..&cod=..", or
        * the bare query "id=..&cod=..".

    Returns ONLY the fields actually present in the page (nothing is invented). On a
    successful parse, ``data`` may include:

        * ``titulo``      -- the heading, e.g. "LEY 13000"
        * ``tipo``        -- norma type, e.g. "LEY"
        * ``numero``      -- norma number, e.g. "13000"
        * ``fecha``       -- date as printed
        * ``descripcion`` -- the norma's description/sumario
        * ``campos``      -- full label->value map (numero, fecha, firmantes, temas,
                            jurisdiccion, etc. -- whatever the page lists)
        * ``archivos``    -- list of {nombre, descripcion, tamanio, url} download links
                            to the full norma text (PDF files)
        * ``source_url``  -- the item.php URL scraped

    Graceful behavior (never raises): a missing/invalid identifier, an unreachable/erroring
    backend, or a page with no recognizable norma block yields an ``{"error": ...}``
    payload that still carries provenance.

    Parameters
    ----------
    norma_url_or_id:
        A SIN item.php URL or "id=..&cod=.." query identifying the norma. The ``cod``
        hash is required.

    Returns
    -------
    dict
        Grounded result (``source_tier="B"``,
        ``citation_flag="[scraped -- verificar contra fuente oficial]"``).
    """
    raw = (norma_url_or_id or "").strip()
    if not raw:
        return _error(
            "missing norma identifier",
            SIN_ITEM_URL,
            detail="provide a SIN item.php URL or 'id=..&cod=..' query",
        )

    source_url = _build_item_url(raw)
    if source_url is None:
        return _error(
            "invalid norma identifier",
            SIN_ITEM_URL,
            detail=(
                "could not extract both 'id' and 'cod' -- the SIN detail page requires "
                "the 'cod' hash; pass the full item_url from santafe_sin_buscar"
            ),
        )

    cache_key = ("norma", source_url)
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

    # item.php serves UTF-8.
    if not response.encoding:
        response.encoding = "utf-8"
    html = response.text

    parsed = _parse_item_html(html, source_url)
    if not parsed:
        return _error(
            "no norma found",
            source_url,
            detail=(
                "the page did not contain a recognizable norma block; the id/cod may be "
                "wrong or expired, or the SIN returned an error page"
            ),
        )

    out = to_dict(
        ground(
            parsed,
            TIER,
            source_url,
            notes=(
                "Scraped from Santa Fe SIN item.php (Tier B). Fields present only when "
                "found in the page; full norma text is at the 'archivos' download URLs."
            ),
        )
    )
    _cache.set(cache_key, out)
    return out


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
