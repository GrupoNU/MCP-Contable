"""Tests for the ckan_nacional connector (datos.gob.ar CKAN Action API, Tier A).

These mock the shared HTTP layer with respx. The connector builds the *full* CKAN
endpoint URL (query string included) and hands it to ``common.fetch`` as the positional
URL -- it does NOT pass ``params=``. So routes are matched here with ``url__startswith``
on ``<BASE>/<action>``, robust to query-string ordering/encoding while still
discriminating between actions.

Live tests (``@pytest.mark.live``) hit the real API and are excluded from CI via
``-m "not live"``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_contable.ckan_nacional import server as ckan
from mcp_contable.common import http as http_mod

BASE = "https://datos.gob.ar/api/3/action"


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Wipe the connector's process-local TTLCache before & after every test."""
    ckan._cache.clear()
    yield
    ckan._cache.clear()


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the HTTP backoff sleep so any retry path is instant (no real delay)."""

    async def _instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(http_mod, "_sleep_backoff", _instant)


def _ckan_ok(result: object) -> dict:
    return {"help": f"{BASE}/help", "success": True, "result": result}


def _ckan_fail(error: object | None = None) -> dict:
    body: dict = {"help": f"{BASE}/help", "success": False}
    if error is not None:
        body["error"] = error
    return body


def _route(action: str) -> str:
    return f"{BASE}/{action}"


def _assert_envelope(out: dict, *, tier: str = "A", citation: str = "") -> None:
    assert set(out) >= {
        "data",
        "source_tier",
        "source_url",
        "retrieved_at",
        "notes",
        "citation_flag",
    }
    assert out["source_tier"] == tier
    assert out["citation_flag"] == citation
    assert out["retrieved_at"]
    assert out["source_url"].startswith("https://datos.gob.ar/")


# --------------------------------------------------------------------------- #
# ckan_list_datasets                                                          #
# --------------------------------------------------------------------------- #


async def test_list_datasets_happy_path() -> None:
    slugs = [
        "sspm-principales-subgrupos-recaudacion-tributaria",
        "registro-mipyme",
        "sspm-recursos-tributarios-totales-por-tributo",
    ]
    with respx.mock:
        route = respx.get(url__startswith=_route("package_list")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(slugs))
        )
        out = await ckan.ckan_list_datasets()

    assert route.called
    _assert_envelope(out)
    assert out["data"]["count"] == 3
    assert out["data"]["datasets"] == slugs


async def test_list_datasets_uses_cache_on_second_call() -> None:
    slugs = ["a", "b"]
    with respx.mock:
        route = respx.get(url__startswith=_route("package_list")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(slugs))
        )
        first = await ckan.ckan_list_datasets()
        second = await ckan.ckan_list_datasets()

    assert route.call_count == 1
    assert first == second


# --------------------------------------------------------------------------- #
# ckan_search_datasets                                                        #
# --------------------------------------------------------------------------- #


async def test_search_datasets_happy_path_ckan_mode() -> None:
    body = _ckan_ok(
        {
            "count": 1,
            "results": [
                {
                    "name": "sspm-principales-subgrupos-recaudacion-tributaria",
                    "title": "Recaudación tributaria",
                    "notes": "Series de recaudación.",
                    "resources": [{"id": "r1"}, {"id": "r2"}],
                },
            ],
        }
    )
    with respx.mock:
        respx.get(url__startswith=_route("package_search")).mock(
            return_value=httpx.Response(200, json=body)
        )
        out = await ckan.ckan_search_datasets("recaudacion", rows=10)

    _assert_envelope(out)
    assert out["data"]["count"] == 1
    assert out["data"]["search_mode"] == "ckan"
    first = out["data"]["results"][0]
    assert first["name"] == "sspm-principales-subgrupos-recaudacion-tributaria"
    assert first["n_resources"] == 2


async def test_search_datasets_client_side_fallback() -> None:
    """count:0 with a non-empty query => paginate q='' and filter client-side."""
    empty = _ckan_ok({"count": 0, "results": []})
    catalog = _ckan_ok(
        {
            "count": 3,
            "results": [
                {
                    "name": "sspm-recaudacion-tributaria",
                    "title": "Recaudación tributaria nacional",
                    "notes": "Impuestos.",
                    "tags": [{"display_name": "tributario"}],
                    "resources": [{"id": "r1"}],
                },
                {
                    "name": "registro-mipyme",
                    "title": "Registro MiPyME",
                    "notes": "Empresas.",
                    "tags": [],
                    "resources": [],
                },
                {
                    "name": "otra-serie-tributaria",
                    "title": "Otra serie tributaria",
                    "notes": "",
                    "tags": [],
                    "resources": [{"id": "x"}],
                },
            ],
        }
    )
    with respx.mock:
        route = respx.get(url__startswith=_route("package_search")).mock(
            side_effect=[
                httpx.Response(200, json=empty),
                httpx.Response(200, json=catalog),
            ]
        )
        out = await ckan.ckan_search_datasets("tributaria")

    assert route.call_count == 2
    _assert_envelope(out)
    assert out["data"]["search_mode"] == "client_side_fallback"
    # Two of three datasets carry "tributaria" in title/slug; MiPyME does not.
    assert out["data"]["count"] == 2
    names = {r["name"] for r in out["data"]["results"]}
    assert names == {"sspm-recaudacion-tributaria", "otra-serie-tributaria"}


async def test_search_datasets_empty_query_stays_ckan_mode() -> None:
    body = _ckan_ok({"count": 0, "results": []})
    with respx.mock:
        route = respx.get(url__startswith=_route("package_search")).mock(
            return_value=httpx.Response(200, json=body)
        )
        out = await ckan.ckan_search_datasets("   ")

    assert route.call_count == 1
    assert out["data"]["search_mode"] == "ckan"
    assert out["data"]["count"] == 0


# --------------------------------------------------------------------------- #
# ckan_get_dataset                                                            #
# --------------------------------------------------------------------------- #


async def test_get_dataset_happy_path_with_resources() -> None:
    pkg = {
        "id": "uuid-1",
        "name": "sspm-principales-subgrupos-recaudacion-tributaria",
        "title": "Recaudación tributaria",
        "notes": "Series.",
        "metadata_created": "2020-01-01T00:00:00",
        "metadata_modified": "2024-01-01T00:00:00",
        "license_title": "CC-BY",
        "author": "SSPM",
        "organization": {"title": "Ministerio de Economía"},
        "tags": [{"display_name": "tributario"}, {"name": "recaudacion"}],
        "groups": [{"display_name": "Economía"}],
        "resources": [
            {
                "id": "res-1",
                "name": "serie.csv",
                "format": "CSV",
                "url": "https://datos.gob.ar/dataset/x/serie.csv",
                "datastore_active": True,
            },
            {
                "id": "res-2",
                "name": "doc.pdf",
                "format": "PDF",
                "url": "https://datos.gob.ar/dataset/x/doc.pdf",
            },
        ],
    }
    with respx.mock:
        respx.get(url__startswith=_route("package_show")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(pkg))
        )
        out = await ckan.ckan_get_dataset(
            "sspm-principales-subgrupos-recaudacion-tributaria"
        )

    _assert_envelope(out)
    data = out["data"]
    assert data["name"] == "sspm-principales-subgrupos-recaudacion-tributaria"
    assert data["organization"] == "Ministerio de Economía"
    assert data["tags"] == ["tributario", "recaudacion"]
    assert data["n_resources"] == 2
    res = data["resources"]
    assert res[0]["datastore_active"] is True
    assert res[1]["datastore_active"] is False


async def test_get_dataset_empty_slug_returns_error() -> None:
    with respx.mock:
        route = respx.get(url__startswith=_route("package_show")).mock(
            return_value=httpx.Response(200, json=_ckan_ok({}))
        )
        out = await ckan.ckan_get_dataset("   ")

    assert not route.called
    _assert_envelope(out)
    assert out["data"]["error"] == "missing dataset slug"


# --------------------------------------------------------------------------- #
# ckan_get_resource_rows                                                      #
# --------------------------------------------------------------------------- #


async def test_get_resource_rows_datastore_success() -> None:
    result = {
        "total": 1500,
        "fields": [{"id": "_id", "type": "int"}, {"id": "monto", "type": "numeric"}],
        "records": [{"_id": 1, "monto": "100"}, {"_id": 2, "monto": "200"}],
    }
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(200, json=_ckan_ok(result))
        )
        out = await ckan.ckan_get_resource_rows("res-uuid", limit=20)

    _assert_envelope(out)
    data = out["data"]
    assert data["datastore_available"] is True
    assert data["total"] == 1500
    assert len(data["records"]) == 2


async def test_get_resource_rows_http_409_is_download_only() -> None:
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(409, json={"success": False})
        )
        out = await ckan.ckan_get_resource_rows("res-uuid")

    _assert_envelope(out)
    assert out["data"]["datastore_available"] is False
    assert "error" not in out["data"]
    assert "message" in out["data"]


async def test_get_resource_rows_success_false_http_200_is_download_only() -> None:
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(200, json=_ckan_fail({"message": "not found"}))
        )
        out = await ckan.ckan_get_resource_rows("res-uuid")

    _assert_envelope(out)
    assert out["data"]["datastore_available"] is False
    assert "error" not in out["data"]


async def test_get_resource_rows_empty_id_returns_error() -> None:
    with respx.mock:
        route = respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(200, json=_ckan_ok({}))
        )
        out = await ckan.ckan_get_resource_rows("")

    assert not route.called
    assert out["data"]["error"] == "missing resource_id"


async def test_get_resource_rows_http_500_returns_error() -> None:
    with respx.mock:
        respx.get(url__startswith=_route("datastore_search")).mock(
            return_value=httpx.Response(500)
        )
        out = await ckan.ckan_get_resource_rows("res-uuid")

    _assert_envelope(out)
    assert "error" in out["data"]


# --------------------------------------------------------------------------- #
# Graceful error handling (never raises to the MCP boundary)                  #
# --------------------------------------------------------------------------- #


async def test_source_unavailable_returns_error_not_raise() -> None:
    with respx.mock:
        respx.get(url__startswith=_route("package_list")).mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        out = await ckan.ckan_list_datasets()

    _assert_envelope(out)
    assert out["data"]["error"] == "source unavailable"


async def test_ckan_success_false_returns_error() -> None:
    with respx.mock:
        respx.get(url__startswith=_route("package_show")).mock(
            return_value=httpx.Response(200, json=_ckan_fail({"message": "Not found"}))
        )
        out = await ckan.ckan_get_dataset("does-not-exist")

    _assert_envelope(out)
    assert out["data"]["error"] == "CKAN reported success=false"


async def test_invalid_json_returns_error() -> None:
    with respx.mock:
        respx.get(url__startswith=_route("package_list")).mock(
            return_value=httpx.Response(200, text="<html>not json</html>")
        )
        out = await ckan.ckan_list_datasets()

    _assert_envelope(out)
    assert out["data"]["error"] == "invalid JSON in CKAN response"


# --------------------------------------------------------------------------- #
# LIVE tests -- hit the real datos.gob.ar API. Excluded from CI.              #
#   Run with:  VIRTUAL_ENV= uv run pytest -m live -v                          #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_list_datasets_returns_real_catalog() -> None:
    out = await ckan.ckan_list_datasets()
    assert "error" not in out["data"], out["data"]
    assert out["source_tier"] == "A"
    assert out["data"]["count"] >= 100


@pytest.mark.live
async def test_live_search_recaudacion_tributaria() -> None:
    out = await ckan.ckan_search_datasets("recaudacion tributaria")
    assert "error" not in out["data"], out["data"]
    assert out["source_tier"] == "A"
    assert out["data"]["count"] >= 1
