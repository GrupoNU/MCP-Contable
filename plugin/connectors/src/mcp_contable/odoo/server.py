"""FastMCP server for Odoo 18 accounting (Tier A) — NU Desarrollos' ERP.

This connector lets the studio OPERATE NU's Odoo (the accounting system, base
``gruponu_production``) over Odoo's official **XML-RPC API**, authenticated with an
**API Key**. It is the link that turns MCP-Contable into a full accounting circuit:
read the chart of accounts / taxes / invoices, and CREATE comprobantes/asientos **in
DRAFT** so a human reviews and posts them in Odoo.

SAFETY MODEL (non-negotiable — base gruponu_production is PRODUCTION)
====================================================================
    * Every write creates records in ``state='draft'``. Odoo does NOT post a draft to
      the ledger until ``action_post`` is called. **This connector NEVER calls
      ``action_post``** — posting stays a human action in Odoo.
    * No tool deletes/modifies an already ``posted`` record. If asked to touch one, it
      refuses with a grounded error.
    * The studio's playbook enforces a confirmation gate before any write; this connector
      additionally flags in every write result that the record is a DRAFT needing review.
    * The DB has TWO companies (NU Desarrollos + Vastu). Reads/writes accept a
      ``company_id`` and default to the configured ``ODOO_COMPANY_ID`` to avoid mixing.

CONFIG (env, gitignored — never in the repo, never logged)
==========================================================
    ODOO_URL        e.g. "https://odoo.gruponu.com" (reachable from the PC over Tailscale)
    ODOO_DB         "gruponu_production"
    ODOO_USER       login of the dedicated API user (e.g. "mcp-contable@gruponu.com")
    ODOO_API_KEY    the user's API Key (replaces the password in xmlrpc auth)
    ODOO_COMPANY_ID (optional) numeric id of NU's company, to scope reads/writes

Design rules honored here (see connectors/CLAUDE.md): every tool returns
``to_dict(ground(...))`` (Tier A), never raw upstream data; tools NEVER raise to the MCP
boundary (failures become grounded, explained error dicts); zero-retention (the API Key,
CUITs and amounts are never logged).
"""

from __future__ import annotations

import os
import socket
import xmlrpc.client
from typing import Any, Optional

from fastmcp import FastMCP

from mcp_contable.common import SourceTier, ground, to_dict

# ---------------------------------------------------------------------------
# Constants / config
# ---------------------------------------------------------------------------

URL_ENV = "ODOO_URL"
DB_ENV = "ODOO_DB"
USER_ENV = "ODOO_USER"
API_KEY_ENV = "ODOO_API_KEY"
COMPANY_ENV = "ODOO_COMPANY_ID"


def _load_local_secrets() -> None:
    """Load credentials from a local secrets file into os.environ, if present.

    Cowork's MCP sandbox does NOT inherit the OS user environment variables; it only
    passes the ``env`` block of the .mcp.json. So secrets (API keys) can't be supplied
    via Windows env vars there. Instead we read them from a local file OUTSIDE the repo:

        ~/.mcp-contable/secrets.env   (simple KEY=value lines; '#' comments allowed)

    The file lives only on the user's machine (never in git, never in the plugin copy),
    so the API key is never published. Values already present in os.environ win (so a
    .mcp.json env or a real OS var can still override). Missing file => no-op.
    """
    path = os.path.join(os.path.expanduser("~"), ".mcp-contable", "secrets.env")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except (OSError, UnicodeDecodeError):
        # No file or unreadable => rely on env vars already set. Never raise.
        pass


# Load local secrets at import time so the tools see ODOO_USER/ODOO_API_KEY in Cowork.
_load_local_secrets()

#: Odoo's API wraps a real, structured ERP => authoritative.
TIER = SourceTier.A

#: Per-call timeout (seconds). First call authenticates; reports can be slow.
RPC_TIMEOUT = 40.0

#: Move types that are NEVER touched/created by safety (posting is human-only).
#: We only ever CREATE in draft; this connector never posts.

mcp = FastMCP("odoo")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _cfg() -> dict[str, Optional[str]]:
    """Read Odoo config from env. Values may be None/empty if unset."""
    return {
        "url": (os.getenv(URL_ENV) or "").strip().rstrip("/") or None,
        "db": (os.getenv(DB_ENV) or "").strip() or None,
        "user": (os.getenv(USER_ENV) or "").strip() or None,
        "api_key": (os.getenv(API_KEY_ENV) or "").strip() or None,
        "company_id": (os.getenv(COMPANY_ENV) or "").strip() or None,
    }


def _source_url(action: str = "") -> str:
    """Human-readable source identifier for grounding (NEVER includes the API key)."""
    url = (os.getenv(URL_ENV) or "<ODOO_URL unset>").strip().rstrip("/")
    db = (os.getenv(DB_ENV) or "?").strip()
    return f"{url}/xmlrpc/2 (db={db}){(' ' + action) if action else ''}"


def _error(
    message: str,
    *,
    detail: str = "",
    action: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Grounded error result (same envelope as success). Never raises."""
    payload: dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    note = f"Odoo request failed: {message}"
    if detail:
        note = f"{note} ({detail})"
    return to_dict(ground(payload, TIER, _source_url(action), notes=note))


def _not_configured_error(action: str) -> dict[str, Any]:
    """Grounded error for missing config (no RPC attempted)."""
    cfg = _cfg()
    missing = [k for k in ("url", "db", "user", "api_key") if not cfg[k]]
    return _error(
        "odoo not configured",
        detail=(
            f"set {', '.join(e for e in (URL_ENV, DB_ENV, USER_ENV, API_KEY_ENV))} "
            f"(missing: {', '.join(missing)}) to use {action}. The connector never guesses."
        ),
        action=action,
    )


# ---------------------------------------------------------------------------
# XML-RPC plumbing (centralized: auth + execute_kw + graceful errors)
# ---------------------------------------------------------------------------


def _proxy(endpoint: str) -> xmlrpc.client.ServerProxy:
    """Build an XML-RPC ServerProxy for /common or /object."""
    url = (os.getenv(URL_ENV) or "").strip().rstrip("/")
    return xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/{endpoint}", allow_none=True)


def _authenticate() -> tuple[Optional[int], Optional[dict[str, Any]]]:
    """Return (uid, error_dict). Exactly one is non-None.

    Uses ``common.authenticate(db, user, api_key, {})`` — the API Key replaces the
    password. A return of falsy uid means bad credentials.
    """
    cfg = _cfg()
    if not all(cfg[k] for k in ("url", "db", "user", "api_key")):
        return None, _not_configured_error("authenticate")
    socket.setdefaulttimeout(RPC_TIMEOUT)
    try:
        common = _proxy("common")
        uid = common.authenticate(cfg["db"], cfg["user"], cfg["api_key"], {})
    except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as exc:
        return None, _error("auth protocol error", detail=type(exc).__name__, action="authenticate")
    except (OSError, socket.timeout) as exc:
        return None, _error("odoo unreachable", detail=type(exc).__name__, action="authenticate")
    finally:
        socket.setdefaulttimeout(None)
    if not uid:
        return None, _error(
            "authentication failed",
            detail="bad ODOO_USER/ODOO_API_KEY, or the user has no access",
            action="authenticate",
        )
    return int(uid), None


def _execute(
    model: str, method: str, args: list, kwargs: Optional[dict] = None
) -> tuple[Any, Optional[dict[str, Any]]]:
    """Run ``models.execute_kw`` after authenticating. Returns (result, error_dict)."""
    uid, err = _authenticate()
    if err is not None:
        return None, err
    cfg = _cfg()
    socket.setdefaulttimeout(RPC_TIMEOUT)
    try:
        models = _proxy("object")
        result = models.execute_kw(
            cfg["db"], uid, cfg["api_key"], model, method, args, kwargs or {}
        )
        return result, None
    except xmlrpc.client.Fault as exc:
        # Odoo business/validation errors arrive as Faults. Surface the message only.
        msg = (getattr(exc, "faultString", "") or "").strip().splitlines()[-1:] or ["fault"]
        return None, _error(
            f"odoo rejected {model}.{method}",
            detail=msg[0][:200],
            action=f"{model}.{method}",
        )
    except xmlrpc.client.ProtocolError as exc:
        return None, _error("odoo protocol error", detail=str(exc.errcode), action=f"{model}.{method}")
    except (OSError, socket.timeout) as exc:
        return None, _error("odoo unreachable", detail=type(exc).__name__, action=f"{model}.{method}")
    finally:
        socket.setdefaulttimeout(None)


def _company_domain() -> list:
    """Domain clause to scope a search to the configured company, or [] if unset.

    For models that still carry a single ``company_id`` (account.tax, account.journal,
    account.move, res.partner...).
    """
    cid = _cfg()["company_id"]
    return [("company_id", "=", int(cid))] if cid and cid.isdigit() else []


def _account_company_domain() -> list:
    """Company scope for ``account.account`` specifically.

    In Odoo 18 the chart of accounts is multi-company: ``account.account`` dropped the
    single ``company_id`` field in favour of a many2many ``company_ids`` (accounts are
    shared across companies). So scoping a chart-of-accounts query uses ``company_ids in
    [cid]`` instead of ``company_id = cid``.
    """
    cid = _cfg()["company_id"]
    return [("company_ids", "in", [int(cid)])] if cid and cid.isdigit() else []


def _ok(data: Any, action: str, notes: str = "") -> dict[str, Any]:
    """Wrap a successful payload as a grounded Tier-A result."""
    return to_dict(ground(data, TIER, _source_url(action), notes=notes))


# ---------------------------------------------------------------------------
# Tools — PHASE 1: READ ONLY (zero risk)
# ---------------------------------------------------------------------------


@mcp.tool
async def odoo_health() -> dict[str, Any]:
    """Check connectivity and credentials to NU's Odoo (read-only, no data touched).

    Calls ``common.version()`` and authenticates with the configured API Key. Use this
    first to confirm the connector reaches Odoo (over Tailscale) and the credentials work.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"reachable", "server_version", "authenticated",
        "uid", "db"}`` on success, or ``{"error": ...}`` if unconfigured/unreachable.
    """
    cfg = _cfg()
    if not cfg["url"]:
        return _not_configured_error("odoo_health")
    socket.setdefaulttimeout(RPC_TIMEOUT)
    version: Any = None
    try:
        version = _proxy("common").version()
    except (OSError, socket.timeout, xmlrpc.client.Error) as exc:
        return _error("odoo unreachable", detail=type(exc).__name__, action="version")
    finally:
        socket.setdefaulttimeout(None)

    uid, err = _authenticate()
    server_version = version.get("server_version") if isinstance(version, dict) else None
    if err is not None:
        # Reachable but auth failed: report that honestly.
        data = {
            "reachable": True,
            "server_version": server_version,
            "authenticated": False,
            "db": cfg["db"],
        }
        return _ok(data, "health", notes="Odoo reachable but authentication failed; check API key.")
    return _ok(
        {
            "reachable": True,
            "server_version": server_version,
            "authenticated": True,
            "uid": uid,
            "db": cfg["db"],
        },
        "health",
        notes="Odoo reachable and authenticated.",
    )


@mcp.tool
async def odoo_get_company() -> dict[str, Any]:
    """List the companies in NU's Odoo database (`res.company`).

    The base ``gruponu_production`` holds more than one company (e.g. NU Desarrollos and
    Vastu). Use this to find the numeric id of NU's company, which scopes the other tools.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"count", "companies": [{id, name, vat, currency}]}``.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_get_company")
    ids, err = _execute("res.company", "search", [[]], {"limit": 20})
    if err is not None:
        return err
    if not ids:
        return _ok({"count": 0, "companies": []}, "res.company", notes="No companies found.")
    rows, err = _execute(
        "res.company", "read", [ids], {"fields": ["id", "name", "vat", "currency_id"]}
    )
    if err is not None:
        return err
    companies = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "vat": r.get("vat"),
            "currency": (r.get("currency_id") or [None, None])[1]
            if isinstance(r.get("currency_id"), list)
            else None,
        }
        for r in (rows or [])
        if isinstance(r, dict)
    ]
    return _ok(
        {"count": len(companies), "companies": companies},
        "res.company",
        notes="Companies in gruponu_production. Use NU's id to scope other tools.",
    )


@mcp.tool
async def odoo_get_plan_cuentas(limit: int = 1000) -> dict[str, Any]:
    """Read the chart of accounts (`account.account`) of NU's company.

    Returns each account's code, name and type. Scoped to ``ODOO_COMPANY_ID`` when set.
    Useful to review whether the standard RI chart fits NU or needs editing.

    Parameters
    ----------
    limit:
        Max accounts to return (clamped 1..2000).

    Returns
    -------
    dict
        Grounded result whose ``data`` is
        ``{"count", "accounts": [{id, code, name, account_type, reconcile}]}`` ordered by code.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_get_plan_cuentas")
    limit = max(1, min(int(limit), 2000))
    # account.account is multi-company in Odoo 18 -> use company_ids (not company_id).
    ids, err = _execute(
        "account.account", "search", [_account_company_domain()], {"limit": limit, "order": "code asc"}
    )
    if err is not None:
        return err
    rows, err = _execute(
        "account.account",
        "read",
        [ids or []],
        {"fields": ["id", "code", "name", "account_type", "reconcile"]},
    )
    if err is not None:
        return err
    accounts = [
        {
            "id": r.get("id"),
            "code": r.get("code"),
            "name": r.get("name"),
            "account_type": r.get("account_type"),
            "reconcile": r.get("reconcile"),
        }
        for r in (rows or [])
        if isinstance(r, dict)
    ]
    return _ok(
        {"count": len(accounts), "accounts": accounts},
        "account.account",
        notes="Chart of accounts (scoped to configured company if ODOO_COMPANY_ID set).",
    )


@mcp.tool
async def odoo_get_impuestos(tipo: str = "") -> dict[str, Any]:
    """List configured taxes (`account.tax`) — e.g. IVA 21/10.5/27, sale/purchase.

    Parameters
    ----------
    tipo:
        Optional filter by use: "sale" (ventas), "purchase" (compras), or "" for both.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"count", "taxes": [{id, name, amount,
        type_tax_use, amount_type}]}``.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_get_impuestos")
    domain = _company_domain()
    if tipo in ("sale", "purchase"):
        domain = domain + [("type_tax_use", "=", tipo)]
    ids, err = _execute("account.tax", "search", [domain], {"limit": 200})
    if err is not None:
        return err
    rows, err = _execute(
        "account.tax",
        "read",
        [ids or []],
        {"fields": ["id", "name", "amount", "type_tax_use", "amount_type"]},
    )
    if err is not None:
        return err
    taxes = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "amount": r.get("amount"),
            "type_tax_use": r.get("type_tax_use"),
            "amount_type": r.get("amount_type"),
        }
        for r in (rows or [])
        if isinstance(r, dict)
    ]
    return _ok({"count": len(taxes), "taxes": taxes}, "account.tax", notes="Configured taxes.")


@mcp.tool
async def odoo_get_diarios() -> dict[str, Any]:
    """List accounting journals (`account.journal`) — ventas, compras, general, banco.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"count", "journals": [{id, name, type, code}]}``.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_get_diarios")
    ids, err = _execute("account.journal", "search", [_company_domain()], {"limit": 100})
    if err is not None:
        return err
    rows, err = _execute(
        "account.journal", "read", [ids or []], {"fields": ["id", "name", "type", "code"]}
    )
    if err is not None:
        return err
    journals = [
        {"id": r.get("id"), "name": r.get("name"), "type": r.get("type"), "code": r.get("code")}
        for r in (rows or [])
        if isinstance(r, dict)
    ]
    return _ok({"count": len(journals), "journals": journals}, "account.journal", notes="Journals.")


@mcp.tool
async def odoo_buscar_partner(query: str) -> dict[str, Any]:
    """Find a partner (`res.partner`) by CUIT (vat) or name.

    Parameters
    ----------
    query:
        A CUIT (digits, with or without dashes) or a (partial) name.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"count", "partners": [{id, name, vat,
        is_company}]}``. Empty list if none found (not an error).
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_buscar_partner")
    q = (query or "").strip()
    if not q:
        return _error("missing query", detail="provide a CUIT or a name", action="res.partner")
    digits = "".join(ch for ch in q if ch.isdigit())
    if len(digits) == 11:
        domain = ["|", ("vat", "=", digits), ("vat", "=", q)]
    else:
        domain = [("name", "ilike", q)]
    ids, err = _execute("res.partner", "search", [domain], {"limit": 30})
    if err is not None:
        return err
    rows, err = _execute(
        "res.partner", "read", [ids or []], {"fields": ["id", "name", "vat", "is_company"]}
    )
    if err is not None:
        return err
    partners = [
        {"id": r.get("id"), "name": r.get("name"), "vat": r.get("vat"), "is_company": r.get("is_company")}
        for r in (rows or [])
        if isinstance(r, dict)
    ]
    return _ok({"count": len(partners), "partners": partners}, "res.partner", notes="Partner search.")


@mcp.tool
async def odoo_get_comprobantes(
    desde: str = "", hasta: str = "", move_type: str = "", estado: str = "", limit: int = 50
) -> dict[str, Any]:
    """Read comprobantes/asientos (`account.move`) — invoices and journal entries.

    Parameters
    ----------
    desde, hasta:
        Optional date range (``YYYY-MM-DD``) on the move ``date``.
    move_type:
        Optional: out_invoice, in_invoice, out_refund, in_refund, entry.
    estado:
        Optional: "draft" or "posted".
    limit:
        Max rows (clamped 1..200).

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"count", "moves": [{id, name, move_type,
        state, partner, invoice_date, amount_total}]}``.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_get_comprobantes")
    limit = max(1, min(int(limit), 200))
    domain = _company_domain()
    if desde:
        domain = domain + [("date", ">=", desde)]
    if hasta:
        domain = domain + [("date", "<=", hasta)]
    if move_type:
        domain = domain + [("move_type", "=", move_type)]
    if estado in ("draft", "posted"):
        domain = domain + [("state", "=", estado)]
    ids, err = _execute(
        "account.move", "search", [domain], {"limit": limit, "order": "date desc, id desc"}
    )
    if err is not None:
        return err
    rows, err = _execute(
        "account.move",
        "read",
        [ids or []],
        {"fields": ["id", "name", "move_type", "state", "partner_id", "invoice_date", "amount_total"]},
    )
    if err is not None:
        return err
    moves = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "move_type": r.get("move_type"),
            "state": r.get("state"),
            "partner": (r.get("partner_id") or [None, None])[1]
            if isinstance(r.get("partner_id"), list)
            else None,
            "invoice_date": r.get("invoice_date"),
            "amount_total": r.get("amount_total"),
        }
        for r in (rows or [])
        if isinstance(r, dict)
    ]
    return _ok({"count": len(moves), "moves": moves}, "account.move", notes="Comprobantes/asientos.")


@mcp.tool
async def odoo_check_l10n_ar() -> dict[str, Any]:
    """Check that the Argentine localization modules are installed (CAE / AFIP support).

    Reads ``ir.module.module`` for ``l10n_ar*`` in state installed.

    Returns
    -------
    dict
        Grounded result whose ``data`` is ``{"installed": [names], "l10n_ar": bool}``.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_check_l10n_ar")
    ids, err = _execute(
        "ir.module.module",
        "search",
        [[("name", "like", "l10n_ar"), ("state", "=", "installed")]],
        {"limit": 50},
    )
    if err is not None:
        return err
    rows, err = _execute("ir.module.module", "read", [ids or []], {"fields": ["name"]})
    if err is not None:
        return err
    names = sorted(r.get("name") for r in (rows or []) if isinstance(r, dict) and r.get("name"))
    return _ok(
        {"installed": names, "l10n_ar": "l10n_ar" in names},
        "ir.module.module",
        notes="Argentine localization modules installed.",
    )


# ---------------------------------------------------------------------------
# Tools — PHASE 2: WRITE IN DRAFT (with consequence gate; never posts)
# ---------------------------------------------------------------------------

_DRAFT_NOTE = (
    "Created as DRAFT in Odoo (state='draft'): it does NOT affect the ledger until a human "
    "reviews and posts it in Odoo. This connector never posts."
)


@mcp.tool
async def odoo_crear_partner_borrador(
    nombre: str, cuit: str = "", es_empresa: bool = True
) -> dict[str, Any]:
    """Create a partner (`res.partner`) — e.g. a supplier — if it does not exist yet.

    Looks up by CUIT first; only creates when not found. Partners have no draft/posted
    state, but this is a low-risk master-data create. Returns the existing or new id.

    Parameters
    ----------
    nombre:
        Razón social / name.
    cuit:
        Optional CUIT (digits).
    es_empresa:
        True for a company (default), False for a person.

    Returns
    -------
    dict
        Grounded result with ``{created: bool, id, name, vat}``.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_crear_partner_borrador")
    nombre = (nombre or "").strip()
    if not nombre:
        return _error("missing nombre", detail="provide the partner name", action="res.partner.create")
    digits = "".join(ch for ch in (cuit or "") if ch.isdigit())
    # Reuse if a partner with this CUIT already exists.
    if len(digits) == 11:
        existing, err = _execute("res.partner", "search", [[("vat", "=", digits)]], {"limit": 1})
        if err is not None:
            return err
        if existing:
            return _ok(
                {"created": False, "id": existing[0], "name": nombre, "vat": digits},
                "res.partner.create",
                notes="Partner already existed (matched by CUIT); not created.",
            )
    vals: dict[str, Any] = {"name": nombre, "is_company": bool(es_empresa)}
    if digits:
        vals["vat"] = digits
    cid = _cfg()["company_id"]
    if cid and cid.isdigit():
        vals["company_id"] = int(cid)
    new_id, err = _execute("res.partner", "create", [vals], {})
    if err is not None:
        return err
    return _ok(
        {"created": True, "id": new_id, "name": nombre, "vat": digits or None},
        "res.partner.create",
        notes="Partner created.",
    )


@mcp.tool
async def odoo_crear_cuenta(code: str, name: str, account_type: str) -> dict[str, Any]:
    """Create an account in the chart of accounts (`account.account`).

    For building/adjusting NU's chart. Refuses if an account with that code already exists.

    Parameters
    ----------
    code:
        Account code (e.g. "411000").
    name:
        Account name.
    account_type:
        Odoo 18 type, e.g. asset_receivable, liability_payable, income, expense, equity,
        asset_cash, asset_current, asset_fixed, liability_current. (Validated by Odoo.)

    Returns
    -------
    dict
        Grounded result with ``{created: bool, id, code, name, account_type}``.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_crear_cuenta")
    code = (code or "").strip()
    name = (name or "").strip()
    account_type = (account_type or "").strip()
    if not (code and name and account_type):
        return _error(
            "missing fields", detail="code, name and account_type are required", action="account.account.create"
        )
    # Don't duplicate an existing code.
    existing, err = _execute("account.account", "search", [[("code", "=", code)]], {"limit": 1})
    if err is not None:
        return err
    if existing:
        return _ok(
            {"created": False, "id": existing[0], "code": code, "name": name, "account_type": account_type},
            "account.account.create",
            notes="An account with that code already exists; not created.",
        )
    vals: dict[str, Any] = {"code": code, "name": name, "account_type": account_type}
    cid = _cfg()["company_id"]
    if cid and cid.isdigit():
        # Odoo 18: account.account is multi-company -> company_ids (m2m), not company_id.
        vals["company_ids"] = [(6, 0, [int(cid)])]
    new_id, err = _execute("account.account", "create", [vals], {})
    if err is not None:
        return err
    return _ok(
        {"created": True, "id": new_id, "code": code, "name": name, "account_type": account_type},
        "account.account.create",
        notes="Account created.",
    )


@mcp.tool
async def odoo_renombrar_cuenta(
    cuenta: str, nuevo_nombre: str = "", nuevo_codigo: str = ""
) -> dict[str, Any]:
    """Rename an account in the chart of accounts (`account.account`).

    Useful for adapting the standard localization chart to NU (e.g. translating
    English names, or assigning a specific bank/account name). Changes ONLY ``name``
    and/or ``code`` of an existing account — never the account type, balances, or any
    accounting data. The change is immediate in Odoo (accounts have no draft state), so
    this is a write to production: the studio's playbook should confirm with the user
    first.

    Parameters
    ----------
    cuenta:
        The account to rename, identified by its numeric id OR by its current code
        (e.g. "111000" / "1.1.1.01.001"). If a code matches more than one account the
        tool refuses (ambiguous).
    nuevo_nombre:
        New ``name`` for the account. Optional (leave empty to keep the current name).
    nuevo_codigo:
        New ``code`` for the account. Optional. If given, the tool refuses when another
        account already uses that code (no duplicates).

    Returns
    -------
    dict
        Grounded result with ``{id, code, name, changed: [fields]}`` on success, or an
        ``{"error": ...}`` payload (account not found, ambiguous, duplicate code, or
        nothing to change).
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_renombrar_cuenta")
    cuenta = (cuenta or "").strip()
    nuevo_nombre = (nuevo_nombre or "").strip()
    nuevo_codigo = (nuevo_codigo or "").strip()
    if not cuenta:
        return _error(
            "missing cuenta",
            detail="provide the account id or its current code",
            action="account.account.write",
        )
    if not nuevo_nombre and not nuevo_codigo:
        return _error(
            "nothing to change",
            detail="provide nuevo_nombre and/or nuevo_codigo",
            action="account.account.write",
        )

    # Resolve the account by id (if numeric) or by code.
    if cuenta.isdigit():
        ids = [int(cuenta)]
    else:
        ids, err = _execute(
            "account.account", "search", [[("code", "=", cuenta)]], {"limit": 2}
        )
        if err is not None:
            return err
        if not ids:
            return _error(
                "account not found", detail=f"no account with code {cuenta!r}", action="account.account.write"
            )
        if len(ids) > 1:
            return _error(
                "ambiguous account",
                detail=f"code {cuenta!r} matches more than one account; use the numeric id",
                action="account.account.write",
            )

    # Read current values (confirm it exists and to report what changes).
    rows, err = _execute(
        "account.account", "read", [ids], {"fields": ["id", "code", "name"]}
    )
    if err is not None:
        return err
    if not rows:
        return _error(
            "account not found", detail=f"no account with id/code {cuenta!r}", action="account.account.write"
        )
    current = rows[0]

    vals: dict[str, Any] = {}
    changed: list[str] = []
    if nuevo_nombre and nuevo_nombre != current.get("name"):
        vals["name"] = nuevo_nombre
        changed.append("name")
    if nuevo_codigo and nuevo_codigo != current.get("code"):
        # Refuse if another account already uses that code.
        dup, err = _execute(
            "account.account",
            "search",
            [[("code", "=", nuevo_codigo), ("id", "!=", current["id"])]],
            {"limit": 1},
        )
        if err is not None:
            return err
        if dup:
            return _error(
                "duplicate code",
                detail=f"another account already uses code {nuevo_codigo!r}",
                action="account.account.write",
            )
        vals["code"] = nuevo_codigo
        changed.append("code")

    if not vals:
        return _ok(
            {
                "id": current["id"],
                "code": current.get("code"),
                "name": current.get("name"),
                "changed": [],
            },
            "account.account.write",
            notes="No change: the new value(s) match the current ones.",
        )

    ok, err = _execute("account.account", "write", [[current["id"]], vals], {})
    if err is not None:
        return err

    return _ok(
        {
            "id": current["id"],
            "code": vals.get("code", current.get("code")),
            "name": vals.get("name", current.get("name")),
            "changed": changed,
            "before": {"code": current.get("code"), "name": current.get("name")},
        },
        "account.account.write",
        notes=(
            "Account renamed in Odoo (immediate, not a draft). Only name/code changed; "
            "no accounting data touched."
        ),
    )


@mcp.tool
async def odoo_crear_factura_borrador(
    move_type: str,
    partner_id: int,
    journal_id: int,
    invoice_date: str,
    lineas: list,
) -> dict[str, Any]:
    """Create an invoice (`account.move`) in DRAFT — NEVER posted.

    Use for loading purchase/sale comprobantes. The move is created in ``state='draft'``;
    a human reviews and posts it in Odoo. This connector never calls ``action_post``.

    Parameters
    ----------
    move_type:
        out_invoice (venta), in_invoice (compra), out_refund, in_refund.
    partner_id:
        Partner id (from odoo_buscar_partner).
    journal_id:
        Journal id (from odoo_get_diarios; purchase/sale as fits move_type).
    invoice_date:
        ``YYYY-MM-DD``.
    lineas:
        List of line dicts: each ``{name, account_id, quantity, price_unit, tax_ids?}``
        where ``tax_ids`` is an optional list of tax ids.

    Returns
    -------
    dict
        Grounded result with ``{id, move_type, state: "draft", n_lineas}`` and a note that
        it is a draft needing human review/posting.
    """
    if not _cfg()["url"]:
        return _not_configured_error("odoo_crear_factura_borrador")
    valid_types = {"out_invoice", "in_invoice", "out_refund", "in_refund"}
    if move_type not in valid_types:
        return _error(
            "invalid move_type",
            detail=f"use one of {sorted(valid_types)}",
            action="account.move.create",
        )
    if not (partner_id and journal_id and invoice_date and isinstance(lineas, list) and lineas):
        return _error(
            "missing fields",
            detail="partner_id, journal_id, invoice_date and a non-empty lineas list are required",
            action="account.move.create",
        )
    # Build invoice_line_ids with ORM (0,0,{...}) commands.
    line_cmds = []
    for ln in lineas:
        if not isinstance(ln, dict):
            return _error("invalid line", detail="each line must be a dict", action="account.move.create")
        vals: dict[str, Any] = {
            "name": str(ln.get("name") or ""),
            "quantity": ln.get("quantity", 1),
            "price_unit": ln.get("price_unit", 0.0),
        }
        if ln.get("account_id"):
            vals["account_id"] = int(ln["account_id"])
        tax_ids = ln.get("tax_ids")
        if isinstance(tax_ids, list) and tax_ids:
            vals["tax_ids"] = [(6, 0, [int(t) for t in tax_ids])]
        line_cmds.append((0, 0, vals))

    move_vals: dict[str, Any] = {
        "move_type": move_type,
        "partner_id": int(partner_id),
        "journal_id": int(journal_id),
        "invoice_date": invoice_date,
        "invoice_line_ids": line_cmds,
        # state='draft' is the default; we NEVER set it to posted and never call action_post.
    }
    cid = _cfg()["company_id"]
    if cid and cid.isdigit():
        move_vals["company_id"] = int(cid)

    new_id, err = _execute("account.move", "create", [move_vals], {})
    if err is not None:
        return err
    return _ok(
        {"id": new_id, "move_type": move_type, "state": "draft", "n_lineas": len(line_cmds)},
        "account.move.create",
        notes=_DRAFT_NOTE,
    )


if __name__ == "__main__":
    # Run as a stdio MCP server. Do NOT invoke this in a non-interactive smoke test --
    # it would block waiting for stdio.
    mcp.run()
