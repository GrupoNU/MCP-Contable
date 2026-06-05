"""Tests for the santafe_sin connector (www.santafe.gov.ar/normativa, Tier B scraper).

These mock the shared HTTP layer with respx. ``santafe_sin_buscar`` POSTs to
``src/busqueda.php`` (matched on ``url__startswith``) and ``santafe_sin_get_norma`` GETs
``item.php`` (also matched on ``url__startswith``).

The cassettes are REAL server fragments captured live during development:
  * ``RESULTS_HTML`` -- the busqueda.php fragment for Ley 13000 (1 result), trimmed.
  * ``NO_RESULTS_HTML`` -- the busqueda.php fragment for a query with 0 matches.
  * ``ITEM_HTML`` -- the item.php detail block for Ley 13000.
All are served as UTF-8 bytes (as the SIN actually serves these two endpoints).

Live tests (``@pytest.mark.live``) hit the real site and are excluded from CI via
``-m "not live"``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_contable.common import http as http_mod
from mcp_contable.santafe_sin import server as sin

BUSQUEDA = "https://www.santafe.gov.ar/normativa/src/busqueda.php"
ITEM = "https://www.santafe.gov.ar/normativa/item.php"


# --------------------------------------------------------------------------- #
# Cassettes (real SIN fragments)                                              #
# --------------------------------------------------------------------------- #

#: Real busqueda.php fragment for Ley 13000 (1 result), trimmed to the parsed region.
RESULTS_HTML = """<div class="row" id="bloqueResultados">
    <div class="row">
        <div class="twelvecol table-responsive last">
            <table class="table table-condensed table-hover table-striped table-bordered">
                <thead>
                    <tr><th colspan="5" scope="col">Resultados</th></tr>
                    <tr>
                        <th><a id="ordenNumero">Número</a></th>
                        <th>Norma legal</th>
                        <th>Descripción</th>
                        <th><a id="ordenFecha">Fecha</a></th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>13000</td>
                        <td>LEY </td>
                        <td>FACULTA AL PODER EJECUTIVO A DISPONER EL INGRESO A LA PLANTA DE PERSONAL.</td>
                        <td style="white-space: nowrap">10-09-2009</td>
                        <td><a title="Visualizar" href="item.php?id=109468&amp;cod=b4d85eaf2515018b25414fd0e2642ea9" class="btn">Ver</a></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    <div class="ui-widget">
        <div class="ui-state-highlight ui-corner-all">
            <p><strong>La consulta ha arrojado 1 resultado.</strong></p>
        </div>
    </div>
</div>"""

#: Real busqueda.php fragment for a query that matches nothing (no <table>).
NO_RESULTS_HTML = """<div class="row" id="bloqueResultados">
    <div class="ui-widget">
        <div class="ui-state-highlight ui-corner-all">
            <p><strong>La consulta ha arrojado 0 resultados.</strong></p>
        </div>
    </div>
</div>"""

#: Real item.php detail block for Ley 13000 (the parsed div.row.form.detalles verbatim).
ITEM_HTML = """<html><head><meta charset="UTF-8"><title>SIN</title></head><body>
<div class="container">
<div class="row form detalles">
    <h3>LEY  13000</h3>
    <div class="row">
        <div class="fourcol "><label>Número: </label><span>13000</span></div>
        <div class="fourcol last"><label>Fecha: </label><span>10-09-2009</span></div>
    </div>
    <div class="row">
        <div class="fourcol last"><label>Firmantes: </label><span>DI POLINA, EDUARDO ALFREDO; BETIQUE, NORBERTO</span></div>
    </div>
    <div class="row">
        <div class="eightcol last"><label>Es promulgada por:</label>
            <span><a href="item.php?id=44352&amp;cod=9687ae7e7bc2a2e1393d61d19f13b000">Decreto 1762/2009</a></span>
        </div>
    </div>
    <div class="row">
        <div class="fourcol last"><label>Temas: </label><span>ADMINISTRACION PUBLICA PROVINCIAL; RECURSOS</span></div>
    </div>
    <div class="row">
        <div class="eightcol last"><label>Descripción: </label><span>FACULTA AL PODER EJECUTIVO A DISPONER EL INGRESO A LA PLANTA DE PERSONAL DE LA ADMINISTRACIÓN PÚBLICA PROVINCIAL.</span></div>
    </div>
    <div class="row">
        <div class="fourcol last"><label>Jurisdicción: </label><span>Poder Legislativo de la Provincia de Santa Fe</span></div>
    </div>
    <div class="row">
        <div class="twelvecol table-responsive last">
            <table class="table table-condensed">
                <thead>
                    <tr><th colspan="5">Texto completo:</th></tr>
                    <tr><th>Archivo</th><th>Descripción</th><th>Tamaño</th><th></th></tr>
                </thead>
                <tbody>
                    <tr>
                        <td>L1300010092009.pdf</td>
                        <td>Ley - Texto Original</td>
                        <td>185.62 kB</td>
                        <td><a href="getFile.php?id=227782&amp;item=109468&amp;cod=424f8677da5f6f3ce07747e97d9273a8" class="btn">Descargar</a></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
</div>
</body></html>"""

#: An item.php error/empty page that lacks the div.row.form.detalles block.
ITEM_EMPTY_HTML = (
    "<html><head><title>SIN</title></head><body>"
    "<div class='container'><p>Norma no encontrada.</p></div>"
    "</body></html>"
)


def _utf8_response(status: int, html: str) -> httpx.Response:
    """Build a response whose body is UTF-8 bytes (as the SIN actually serves these)."""
    return httpx.Response(
        status,
        content=html.encode("utf-8"),
        headers={"Content-Type": "text/html; charset=UTF-8"},
    )


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Wipe the connector's process-local TTLCache before & after every test."""
    sin._cache.clear()
    yield
    sin._cache.clear()


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the HTTP backoff sleep so any retry path is instant (no real delay)."""

    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


def _assert_envelope(out: dict) -> None:
    """Common grounding-envelope assertions for every sin tool result (Tier B)."""
    assert set(out) >= {
        "data",
        "source_tier",
        "source_url",
        "retrieved_at",
        "notes",
        "citation_flag",
    }
    assert out["source_tier"] == "B"
    # Tier B always carries the scraped-verification marker.
    assert out["citation_flag"] == "[scraped -- verificar contra fuente oficial]"
    assert out["retrieved_at"]
    assert out["source_url"].startswith("https://www.santafe.gov.ar/normativa/")


# --------------------------------------------------------------------------- #
# santafe_sin_buscar -- happy path                                            #
# --------------------------------------------------------------------------- #


async def test_buscar_happy_path_parses_results() -> None:
    with respx.mock:
        route = respx.post(url__startswith=BUSQUEDA).mock(
            return_value=_utf8_response(200, RESULTS_HTML)
        )
        out = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")

    assert route.called
    _assert_envelope(out)
    data = out["data"]
    assert "error" not in data
    assert data["total"] == 1
    assert data["count"] == 1
    assert len(data["results"]) == 1
    row = data["results"][0]
    assert row["numero"] == "13000"
    assert row["tipo"] == "LEY"
    assert row["fecha"] == "10-09-2009"
    assert row["descripcion"].startswith("FACULTA AL PODER EJECUTIVO")
    assert row["id"] == "109468"
    assert row["cod"] == "b4d85eaf2515018b25414fd0e2642ea9"
    assert row["item_url"] == (
        "https://www.santafe.gov.ar/normativa/"
        "item.php?id=109468&cod=b4d85eaf2515018b25414fd0e2642ea9"
    )
    # The echoed query reflects the normalized filters.
    assert data["query"]["numero"] == "13000"


async def test_buscar_sends_tiponorma_and_omits_tema() -> None:
    """The POST must map tipo->tipoNorma value and must NOT include 'tema[]' (400 bug)."""
    captured: dict = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _utf8_response(200, RESULTS_HTML)

    with respx.mock:
        respx.post(url__startswith=BUSQUEDA).mock(side_effect=_capture)
        await sin.santafe_sin_buscar(tipo="Decreto", numero="100", anio="2020")

    url = captured["url"]
    assert "tipoNorma=2" in url  # Decreto -> 2
    assert "numNorma=100" in url
    assert "anio=2020" in url
    assert "tema" not in url  # never send tema[] (empty value triggers HTTP 400)


async def test_buscar_uses_cache_on_second_call() -> None:
    with respx.mock:
        route = respx.post(url__startswith=BUSQUEDA).mock(
            return_value=_utf8_response(200, RESULTS_HTML)
        )
        first = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")
        second = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")

    assert route.call_count == 1
    assert first == second


async def test_buscar_defaults_tipo_to_ley_when_omitted() -> None:
    with respx.mock:
        respx.post(url__startswith=BUSQUEDA).mock(
            return_value=_utf8_response(200, RESULTS_HTML)
        )
        out = await sin.santafe_sin_buscar(numero="13000")

    _assert_envelope(out)
    assert "default" in out["data"]["query"]["tipo"].lower()
    assert "defaulted to 'Ley'" in out["notes"]


# --------------------------------------------------------------------------- #
# santafe_sin_buscar -- no results & graceful failures                        #
# --------------------------------------------------------------------------- #


async def test_buscar_no_results_is_graceful() -> None:
    """A 0-match query returns an empty result set, NOT an error."""
    with respx.mock:
        respx.post(url__startswith=BUSQUEDA).mock(
            return_value=_utf8_response(200, NO_RESULTS_HTML)
        )
        out = await sin.santafe_sin_buscar(tipo="Ley", numero="9999999")

    _assert_envelope(out)
    data = out["data"]
    assert "error" not in data
    assert data["total"] == 0
    assert data["count"] == 0
    assert data["results"] == []


async def test_buscar_empty_query_returns_error_no_http() -> None:
    with respx.mock:
        route = respx.post(url__startswith=BUSQUEDA).mock(
            return_value=_utf8_response(200, RESULTS_HTML)
        )
        out = await sin.santafe_sin_buscar()

    assert not route.called
    _assert_envelope(out)
    assert out["data"]["error"] == "empty query"


async def test_buscar_unknown_tipo_returns_error_no_http() -> None:
    with respx.mock:
        route = respx.post(url__startswith=BUSQUEDA).mock(
            return_value=_utf8_response(200, RESULTS_HTML)
        )
        out = await sin.santafe_sin_buscar(tipo="Ordenanza", numero="1")

    assert not route.called
    assert out["data"]["error"] == "unknown tipo"


async def test_buscar_source_unavailable_returns_error() -> None:
    with respx.mock:
        respx.post(url__startswith=BUSQUEDA).mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        out = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


async def test_buscar_http_400_returns_error() -> None:
    """A non-retryable 400 (the tema[] quirk) surfaces as a graceful error dict."""
    with respx.mock:
        respx.post(url__startswith=BUSQUEDA).mock(return_value=httpx.Response(400))
        out = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")

    _assert_envelope(out)
    assert "error" in out["data"]
    assert out["data"]["status_code"] == 400


async def test_buscar_http_503_exhausts_retries_to_error() -> None:
    with respx.mock:
        respx.post(url__startswith=BUSQUEDA).mock(return_value=httpx.Response(503))
        out = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


# --------------------------------------------------------------------------- #
# santafe_sin_get_norma -- happy path                                         #
# --------------------------------------------------------------------------- #


async def test_get_norma_happy_path_parses_fields() -> None:
    item_url = (
        "https://www.santafe.gov.ar/normativa/"
        "item.php?id=109468&cod=b4d85eaf2515018b25414fd0e2642ea9"
    )
    with respx.mock:
        route = respx.get(url__startswith=ITEM).mock(
            return_value=_utf8_response(200, ITEM_HTML)
        )
        out = await sin.santafe_sin_get_norma(item_url)

    assert route.called
    _assert_envelope(out)
    data = out["data"]
    assert "error" not in data
    assert data["titulo"] == "LEY 13000"
    assert data["tipo"] == "LEY"
    assert data["numero"] == "13000"
    assert data["campos"]["fecha"] == "10-09-2009"
    assert "DI POLINA" in data["campos"]["firmantes"]
    assert data["campos"]["temas"].startswith("ADMINISTRACION PUBLICA")
    # UTF-8 accents survive round-trip in the description.
    assert "ADMINISTRACIÓN PÚBLICA" in data["descripcion"]
    # The full-text download link is captured.
    assert data["archivos"][0]["nombre"] == "L1300010092009.pdf"
    assert data["archivos"][0]["url"].startswith(
        "https://www.santafe.gov.ar/normativa/getFile.php?id=227782"
    )


async def test_get_norma_accepts_relative_and_bare_query() -> None:
    with respx.mock:
        respx.get(url__startswith=ITEM).mock(
            return_value=_utf8_response(200, ITEM_HTML)
        )
        out_rel = await sin.santafe_sin_get_norma(
            "item.php?id=109468&cod=b4d85eaf2515018b25414fd0e2642ea9"
        )
        sin._cache.clear()
        out_bare = await sin.santafe_sin_get_norma(
            "id=109468&cod=b4d85eaf2515018b25414fd0e2642ea9"
        )

    assert out_rel["data"]["numero"] == "13000"
    assert out_bare["data"]["numero"] == "13000"


# --------------------------------------------------------------------------- #
# santafe_sin_get_norma -- graceful failures                                  #
# --------------------------------------------------------------------------- #


async def test_get_norma_missing_id_returns_error_no_http() -> None:
    with respx.mock:
        route = respx.get(url__startswith=ITEM).mock(
            return_value=_utf8_response(200, ITEM_HTML)
        )
        out = await sin.santafe_sin_get_norma("   ")

    assert not route.called
    assert out["data"]["error"] == "missing norma identifier"


async def test_get_norma_without_cod_returns_error_no_http() -> None:
    """item.php requires the 'cod' hash; a bare id is rejected before any HTTP."""
    with respx.mock:
        route = respx.get(url__startswith=ITEM).mock(
            return_value=_utf8_response(200, ITEM_HTML)
        )
        out = await sin.santafe_sin_get_norma("item.php?id=109468")

    assert not route.called
    assert out["data"]["error"] == "invalid norma identifier"


async def test_get_norma_empty_html_returns_graceful_error() -> None:
    with respx.mock:
        respx.get(url__startswith=ITEM).mock(
            return_value=_utf8_response(200, ITEM_EMPTY_HTML)
        )
        out = await sin.santafe_sin_get_norma(
            "id=109468&cod=deadbeefdeadbeefdeadbeefdeadbeef"
        )

    _assert_envelope(out)
    assert out["data"]["error"] == "no norma found"


async def test_get_norma_source_unavailable_returns_error() -> None:
    with respx.mock:
        respx.get(url__startswith=ITEM).mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        out = await sin.santafe_sin_get_norma(
            "id=109468&cod=b4d85eaf2515018b25414fd0e2642ea9"
        )

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


# --------------------------------------------------------------------------- #
# LIVE tests -- hit the real SIN site. Excluded from CI.                       #
#   Run with:  VIRTUAL_ENV= uv run pytest tests/test_santafe_sin.py -m live -v #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_buscar_finds_ley_13000() -> None:
    """Hit the real busqueda.php and verify Ley 13000 is found and parsed."""
    out = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")
    assert out["source_tier"] == "B"
    assert out["citation_flag"] == "[scraped -- verificar contra fuente oficial]"

    data = out["data"]
    if "error" in data:
        pytest.skip(f"Santa Fe SIN unavailable at test time: {data}")

    assert data["total"] >= 1
    assert data["results"], "expected at least one result row"
    row = data["results"][0]
    assert row["numero"] == "13000"
    assert "item.php" in row["item_url"]
    assert row.get("cod"), "the detail link must carry the cod hash"


@pytest.mark.live
async def test_live_get_norma_roundtrip_from_search() -> None:
    """Search live, then fetch the first result's detail page and verify extraction."""
    found = await sin.santafe_sin_buscar(tipo="Ley", numero="13000")
    if "error" in found["data"] or not found["data"].get("results"):
        pytest.skip(f"Santa Fe SIN search unavailable: {found['data']}")

    item_url = found["data"]["results"][0]["item_url"]
    out = await sin.santafe_sin_get_norma(item_url)
    assert out["source_tier"] == "B"

    data = out["data"]
    if "error" in data:
        pytest.skip(f"Santa Fe SIN detail unavailable: {data}")

    blob = " ".join(str(v) for v in data.values()).lower()
    assert data.get("numero") == "13000" or "ley" in blob
    assert data.get("source_url", out["source_url"]).startswith(
        "https://www.santafe.gov.ar/normativa/"
    )
