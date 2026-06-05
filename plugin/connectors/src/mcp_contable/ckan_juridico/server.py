"""FastMCP server for the CKAN Action API of datos.jus.gob.ar (Tier A).

In MCP-Contable this connector's main job is to **find the InfoLEG id of a national
fiscal norm** (Ley de IVA 23.349, Ganancias 20.628, Monotributo 24.977, Procedimiento
Tributario 11.683, etc.) via the dataset ``base-de-datos-legislativos-infoleg`` -- that
id is then fed to the ``infoleg`` connector to retrieve the norm's text. It wraps the
official CKAN Action API of Argentina's Ministry of Justice open-data portal and exposes
a small set of tools to discover datasets, inspect metadata/resources, and read datastore
rows.

Design rules honored here (see connectors/CLAUDE.md):

    * All HTTP goes through ``common.fetch`` -- never instantiate ``httpx`` directly.
      That preserves the project's zero-retention guarantee.
    * Every tool returns ``to_dict(ground(...))`` with ``SourceTier.A`` -- never raw
      upstream data.
    * Tools NEVER raise to the MCP boundary. Any failure (source unreachable, bad
      status, invalid JSON, or CKAN ``success: false``) is turned into a grounded,
      explained error dict so Claude can reason about it.

ABOUT THE FULL-TEXT SEARCH (``q=``)
===================================
The portal's Solr full-text index behaves poorly for legal terms: a query like
``q=jurisprudencia`` returns ``count: 0`` even though relevant datasets exist. The
search tool therefore (a) documents this limitation prominently, (b) steers callers
toward ``ckan_list_datasets`` + title/slug filtering for topical discovery, and
(c) when a ``q=`` search yields zero hits, performs a *local* fallback: it pages the
full dataset list with an empty query and filters titles/names/notes/tags client-side
for the query terms. That fallback is flagged in the result ``notes``.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlencode

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

#: Base URL of the CKAN Action API. Every endpoint is ``<BASE>/<action>``.
CKAN_BASE = "https://datos.jus.gob.ar/api/3/action"

#: Tier for this whole connector: an official, structured API => authoritative.
TIER = SourceTier.A

#: Per-request timeout (seconds). Generous: the datastore can be slow for big rows.
HTTP_TIMEOUT = 30.0

#: TTL for cacheable, slow-moving responses (package_list / package_show), in seconds.
#: 15 minutes balances freshness against not re-hitting the portal for repeat lookups.
_CACHE_TTL = 900.0

#: Process-local cache. Safe per common/cache.py (single event loop, no persistence).
_cache = TTLCache(default_ttl=_CACHE_TTL)

mcp = FastMCP("ckan-juridico")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _endpoint_url(action: str, params: Optional[dict[str, Any]] = None) -> str:
    """Build the full, human-readable CKAN endpoint URL (used as ``source_url``).

    The query string is included so the grounded ``source_url`` is the exact URL a
    human could paste into a browser to reproduce the call.
    """
    url = f"{CKAN_BASE}/{action}"
    if params:
        # Drop empty/None values so the citation URL stays clean.
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url = f"{url}?{urlencode(clean)}"
    return url


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
    note = f"CKAN request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, source_url, notes=note))


async def _ckan_get(
    action: str, params: Optional[dict[str, Any]] = None
) -> tuple[Optional[Any], Optional[dict[str, Any]]]:
    """Call a CKAN action and return ``(result, error_dict)``.

    Exactly one of the two is non-None:

        * ``(result, None)``   -> CKAN returned ``success: true``; ``result`` is its
          unwrapped ``result`` field.
        * ``(None, error_dict)`` -> a grounded error dict ready to return from a tool.

    Every failure mode is mapped here so the tools stay tiny and never raise:
    source unreachable, non-retryable HTTP status, invalid JSON, and CKAN-level
    ``success: false``.
    """
    source_url = _endpoint_url(action, params)
    try:
        response = await fetch(source_url, timeout=HTTP_TIMEOUT)
    except SourceUnavailableError as exc:
        return None, _error(
            "source unavailable",
            source_url,
            detail=str(exc),
        )
    except SourceResponseError as exc:
        return None, _error(
            f"upstream returned HTTP {exc.status_code}",
            source_url,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return None, _error(
            "invalid JSON in CKAN response",
            source_url,
            detail=type(exc).__name__,
        )

    # CKAN signals logical failure with success:false and an "error" object, even on
    # HTTP 200. Treat that as a graceful error, not a crash.
    if not isinstance(body, dict) or not body.get("success", False):
        ckan_error = body.get("error") if isinstance(body, dict) else None
        return None, _error(
            "CKAN reported success=false",
            source_url,
            detail=json.dumps(ckan_error) if ckan_error else "no error detail",
        )

    return body.get("result"), None


def _summarize_dataset(pkg: dict[str, Any]) -> dict[str, Any]:
    """Reduce a full CKAN package to a compact, search-result-friendly summary."""
    notes = (pkg.get("notes") or "").strip()
    truncated = notes if len(notes) <= 280 else notes[:277] + "..."
    resources = pkg.get("resources") or []
    return {
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "notes": truncated,
        "n_resources": len(resources),
    }


def _matches_terms(pkg: dict[str, Any], terms: list[str]) -> bool:
    """Client-side fallback match: do all query terms appear in the package text?

    Searches title, name (slug), notes and tag names, case-insensitively. Used only
    when CKAN's broken full-text index returns zero hits.
    """
    haystack_parts = [
        pkg.get("title") or "",
        pkg.get("name") or "",
        pkg.get("notes") or "",
    ]
    for tag in pkg.get("tags") or []:
        if isinstance(tag, dict):
            haystack_parts.append(tag.get("display_name") or tag.get("name") or "")
    haystack = " ".join(haystack_parts).lower()
    return all(term in haystack for term in terms)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def ckan_list_datasets() -> dict[str, Any]:
    """List the slugs (identifiers) of every dataset on datos.jus.gob.ar.

    Calls CKAN ``package_list``. This is the best starting point for discovery: it
    returns the full catalog (~63 dataset slugs) as plain strings, e.g.
    ``"base-de-datos-legislativos-infoleg"``. Pass any of those slugs to
    ``ckan_get_dataset`` to inspect metadata and downloadable resources.

    Prefer this over ``ckan_search_datasets`` when you want to browse the whole
    catalog, because the portal's full-text search is unreliable for legal terms.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"count": int, "datasets": [slug, ...]}``.
    """
    cache_key = ("package_list",)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result, err = await _ckan_get("package_list")
    if err is not None:
        return err

    slugs = result if isinstance(result, list) else []
    source_url = _endpoint_url("package_list")
    out = to_dict(
        ground(
            {"count": len(slugs), "datasets": slugs},
            TIER,
            source_url,
            notes="Full dataset catalog (CKAN package_list).",
        )
    )
    _cache.set(cache_key, out)
    return out


@mcp.tool
async def ckan_search_datasets(
    query: str, rows: int = 10, start: int = 0
) -> dict[str, Any]:
    """Search datasets on datos.jus.gob.ar (CKAN ``package_search``).

    IMPORTANT -- full-text search is UNRELIABLE here. The portal's Solr index matches
    legal terms poorly: e.g. ``query="jurisprudencia"`` returns zero hits even though
    relevant datasets exist. For topical discovery, prefer ``ckan_list_datasets`` and
    filter the slugs by keyword yourself, or search for words that appear literally in
    a dataset *title*.

    To mitigate the index problem, when a server-side ``q=`` search returns zero
    results this tool automatically falls back to a CLIENT-SIDE scan: it pages the
    catalog with an empty query and matches your terms against each dataset's title,
    slug, notes and tags. When that fallback is used it is flagged in ``notes`` and the
    payload's ``search_mode`` is ``"client_side_fallback"``.

    Parameters
    ----------
    query:
        Free-text query. May be empty to simply page through all datasets.
    rows:
        Max number of results to return (page size). Clamped to 1..100.
    start:
        Zero-based offset for pagination.

    Returns
    -------
    dict
        Grounded result whose ``data`` is::

            {
                "count": <total matches>,
                "search_mode": "ckan" | "client_side_fallback",
                "results": [{name, title, notes, n_resources}, ...],
            }
    """
    rows = max(1, min(rows, 100))
    start = max(0, start)
    params = {"q": query, "rows": rows, "start": start}
    source_url = _endpoint_url("package_search", params)

    result, err = await _ckan_get("package_search", params)
    if err is not None:
        return err

    result = result if isinstance(result, dict) else {}
    count = int(result.get("count", 0) or 0)
    raw_results = result.get("results") or []
    summarized = [
        _summarize_dataset(pkg) for pkg in raw_results if isinstance(pkg, dict)
    ]

    # Happy path: CKAN actually found something.
    if count > 0 or not query.strip():
        return to_dict(
            ground(
                {
                    "count": count,
                    "search_mode": "ckan",
                    "results": summarized,
                },
                TIER,
                source_url,
                notes=(
                    "CKAN package_search. Note: full-text search is unreliable for "
                    "legal terms; for topical discovery prefer ckan_list_datasets."
                ),
            )
        )

    # Fallback: q= matched nothing. Scan the catalog client-side.
    fallback = await _client_side_search(query, rows, start, source_url)
    return fallback


async def _client_side_search(
    query: str, rows: int, start: int, source_url: str
) -> dict[str, Any]:
    """Page the whole catalog with q='' and filter datasets client-side by ``query``.

    Used only when CKAN's broken full-text index returns zero hits. Honors the same
    ``rows``/``start`` paging contract as the server-side search, applied AFTER the
    client-side filter.
    """
    terms = [t for t in query.lower().split() if t]
    # Pull a wide page of the catalog (CKAN caps page size; 1000 covers ~63 datasets).
    wide_params = {"q": "", "rows": 1000, "start": 0}
    result, err = await _ckan_get("package_search", wide_params)
    if err is not None:
        # Surface the underlying error but keep the caller's intended source_url.
        err["data"]["search_mode"] = "client_side_fallback"
        err["source_url"] = source_url
        return err

    result = result if isinstance(result, dict) else {}
    all_pkgs = [p for p in (result.get("results") or []) if isinstance(p, dict)]
    matched = [p for p in all_pkgs if _matches_terms(p, terms)]
    page = matched[start : start + rows]
    summarized = [_summarize_dataset(pkg) for pkg in page]

    return to_dict(
        ground(
            {
                "count": len(matched),
                "search_mode": "client_side_fallback",
                "results": summarized,
            },
            TIER,
            source_url,
            notes=(
                "CKAN full-text search returned 0 hits for this query (its index is "
                "unreliable for legal terms). Results below come from a client-side "
                "scan of dataset titles/slugs/notes/tags via package_search(q='')."
            ),
        )
    )


@mcp.tool
async def ckan_get_dataset(slug: str) -> dict[str, Any]:
    """Fetch a dataset's full metadata and its downloadable resources.

    Calls CKAN ``package_show`` for the given ``slug`` (a dataset ``name``, e.g.
    ``"base-de-datos-legislativos-infoleg"`` -- obtain slugs from
    ``ckan_list_datasets`` or ``ckan_search_datasets``).

    The substantive legal data usually lives in the resources' downloadable CSV files:
    use each resource's ``url`` to download it, or try ``ckan_get_resource_rows`` with
    a resource ``id`` to read rows directly when that resource is in CKAN's datastore.

    Parameters
    ----------
    slug:
        The dataset ``name`` / slug to look up.

    Returns
    -------
    dict
        Grounded result whose ``data`` carries dataset metadata plus a ``resources``
        list of ``{id, name, format, url, datastore_active}`` entries.
    """
    slug = (slug or "").strip()
    if not slug:
        return _error(
            "missing dataset slug",
            _endpoint_url("package_show"),
            detail="provide a dataset slug, e.g. from ckan_list_datasets",
        )

    cache_key = ("package_show", slug)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    params = {"id": slug}
    source_url = _endpoint_url("package_show", params)
    result, err = await _ckan_get("package_show", params)
    if err is not None:
        return err

    pkg = result if isinstance(result, dict) else {}
    resources = []
    for res in pkg.get("resources") or []:
        if not isinstance(res, dict):
            continue
        resources.append(
            {
                "id": res.get("id"),
                "name": res.get("name"),
                "format": res.get("format"),
                "url": res.get("url"),
                # Hint for ckan_get_resource_rows: only datastore-active resources
                # can be queried row-by-row; others are CSV download only.
                "datastore_active": bool(res.get("datastore_active", False)),
            }
        )

    org = pkg.get("organization") or {}
    data = {
        "id": pkg.get("id"),
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "notes": pkg.get("notes"),
        "metadata_created": pkg.get("metadata_created"),
        "metadata_modified": pkg.get("metadata_modified"),
        "license_title": pkg.get("license_title"),
        "author": pkg.get("author"),
        "organization": org.get("title") if isinstance(org, dict) else None,
        "tags": [
            t.get("display_name") or t.get("name")
            for t in (pkg.get("tags") or [])
            if isinstance(t, dict)
        ],
        "groups": [
            g.get("display_name") or g.get("name")
            for g in (pkg.get("groups") or [])
            if isinstance(g, dict)
        ],
        "n_resources": len(resources),
        "resources": resources,
    }

    out = to_dict(
        ground(
            data,
            TIER,
            source_url,
            notes="CKAN package_show. Substantive data lives in the resource CSV urls.",
        )
    )
    _cache.set(cache_key, out)
    return out


@mcp.tool
async def ckan_get_resource_rows(
    resource_id: str, limit: int = 20, query: str = ""
) -> dict[str, Any]:
    """Read rows from a dataset resource via CKAN's datastore (``datastore_search``).

    Many resources on datos.jus.gob.ar are NOT loaded into the queryable datastore --
    they are published only as downloadable CSV files. For those, CKAN returns an
    error (typically HTTP 409 / ``success: false``); this tool handles that
    gracefully: instead of failing, it returns an explanatory result telling you the
    resource is download-only and, when possible, the CSV ``url`` to fetch instead
    (looked up via ``package_show`` is NOT done here to stay cheap -- use
    ``ckan_get_dataset`` to get the url).

    Parameters
    ----------
    resource_id:
        The resource ``id`` (a UUID, obtained from ``ckan_get_dataset``).
    limit:
        Max rows to return. Clamped to 1..100.
    query:
        Optional free-text filter passed to the datastore (``q=``). Empty returns the
        first ``limit`` rows.

    Returns
    -------
    dict
        Grounded result. On success ``data`` is
        ``{"total": int, "fields": [...], "records": [...]}``; for a download-only
        resource ``data`` explains that and includes ``datastore_available: false``.
    """
    resource_id = (resource_id or "").strip()
    if not resource_id:
        return _error(
            "missing resource_id",
            _endpoint_url("datastore_search"),
            detail="provide a resource id, e.g. from ckan_get_dataset",
        )

    limit = max(1, min(limit, 100))
    params: dict[str, Any] = {"resource_id": resource_id, "limit": limit}
    if query:
        params["q"] = query
    source_url = _endpoint_url("datastore_search", params)

    try:
        response = await fetch(source_url, timeout=HTTP_TIMEOUT)
    except SourceResponseError as exc:
        # 404/409 here almost always means "resource not in the datastore" -> the
        # resource is CSV-download-only. Return that as a normal, explained result.
        if exc.status_code in (404, 409):
            return to_dict(
                ground(
                    {
                        "datastore_available": False,
                        "resource_id": resource_id,
                        "message": (
                            "This resource is not loaded into CKAN's datastore, so "
                            "its rows cannot be queried directly. It is published as a "
                            "downloadable file. Use ckan_get_dataset to obtain the "
                            "resource's CSV 'url' and download it instead."
                        ),
                    },
                    TIER,
                    source_url,
                    notes=(
                        f"datastore_search returned HTTP {exc.status_code}: resource "
                        "is download-only (not in datastore)."
                    ),
                )
            )
        return _error(
            f"upstream returned HTTP {exc.status_code}",
            source_url,
            detail=str(exc),
            extra={"status_code": exc.status_code},
        )
    except SourceUnavailableError as exc:
        return _error("source unavailable", source_url, detail=str(exc))

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return _error(
            "invalid JSON in CKAN response",
            source_url,
            detail=type(exc).__name__,
        )

    # CKAN may answer HTTP 200 with success:false when the resource is not in the
    # datastore. Treat that the same as the 409 case above (download-only).
    if not isinstance(body, dict) or not body.get("success", False):
        return to_dict(
            ground(
                {
                    "datastore_available": False,
                    "resource_id": resource_id,
                    "message": (
                        "This resource is not queryable via the datastore (CKAN "
                        "reported success=false). It is likely download-only; use "
                        "ckan_get_dataset to obtain its CSV 'url'."
                    ),
                },
                TIER,
                source_url,
                notes="datastore_search success=false: resource is download-only.",
            )
        )

    result = body.get("result") or {}
    fields = result.get("fields") or []
    records = result.get("records") or []
    data = {
        "datastore_available": True,
        "resource_id": resource_id,
        "total": result.get("total"),
        "fields": [
            {"id": f.get("id"), "type": f.get("type")}
            for f in fields
            if isinstance(f, dict)
        ],
        "records": records,
    }
    return to_dict(
        ground(
            data,
            TIER,
            source_url,
            notes="CKAN datastore_search rows.",
        )
    )


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
