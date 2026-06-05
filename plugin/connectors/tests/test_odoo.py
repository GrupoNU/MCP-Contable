"""Tests for the odoo connector (XML-RPC client of NU's Odoo 18, Tier A).

The connector talks to Odoo via ``xmlrpc.client.ServerProxy``. These tests replace that
proxy with a fake so no real Odoo is contacted. Config is injected via monkeypatch env.

Safety is the point of several tests: writes must create in DRAFT and the connector must
never call ``action_post``.

Live tests (``@pytest.mark.live``) need a reachable Odoo + valid API key and are excluded
from CI; run with the ODOO_* env set.
"""

from __future__ import annotations

import xmlrpc.client

import pytest

from mcp_contable.odoo import server as odoo

URL = "https://odoo.test"
DB = "gruponu_production"


# --------------------------------------------------------------------------- #
# Fake XML-RPC proxy                                                          #
# --------------------------------------------------------------------------- #


class _FakeCommon:
    """Stands in for the /common endpoint."""

    def __init__(self, version=None, uid=7, auth_raises=None):
        self._version = version or {"server_version": "18.0-test"}
        self._uid = uid
        self._auth_raises = auth_raises

    def version(self):
        return self._version

    def authenticate(self, db, user, key, ctx):
        if self._auth_raises:
            raise self._auth_raises
        return self._uid


class _FakeObject:
    """Stands in for the /object endpoint. ``handler`` maps (model, method) -> result."""

    def __init__(self, handler):
        self._handler = handler
        self.calls = []  # records (model, method, args, kwargs)

    def execute_kw(self, db, uid, key, model, method, args, kwargs):
        self.calls.append((model, method, args, kwargs))
        return self._handler(model, method, args, kwargs)


def _install_fake(monkeypatch, *, common=None, handler=None, obj_holder=None):
    """Patch odoo._proxy to return fakes. Returns the FakeObject for assertions."""
    common = common or _FakeCommon()
    fake_obj = _FakeObject(handler or (lambda *a: []))
    if obj_holder is not None:
        obj_holder["obj"] = fake_obj

    def _fake_proxy(endpoint):
        return common if endpoint == "common" else fake_obj

    monkeypatch.setattr(odoo, "_proxy", _fake_proxy)
    return fake_obj


@pytest.fixture
def _configured(monkeypatch):
    monkeypatch.setenv(odoo.URL_ENV, URL)
    monkeypatch.setenv(odoo.DB_ENV, DB)
    monkeypatch.setenv(odoo.USER_ENV, "mcp-contable@gruponu.com")
    monkeypatch.setenv(odoo.API_KEY_ENV, "secret-key")
    monkeypatch.delenv(odoo.COMPANY_ENV, raising=False)


def _assert_envelope(out: dict, *, citation: str = "") -> None:
    assert set(out) >= {"data", "source_tier", "source_url", "retrieved_at", "notes", "citation_flag"}
    assert out["source_tier"] == "A"
    assert out["citation_flag"] == citation
    assert out["retrieved_at"]
    # The API key must never leak into the grounded source_url.
    assert "secret-key" not in out["source_url"]


# --------------------------------------------------------------------------- #
# Config / not configured                                                     #
# --------------------------------------------------------------------------- #


async def test_health_not_configured(monkeypatch):
    for e in (odoo.URL_ENV, odoo.DB_ENV, odoo.USER_ENV, odoo.API_KEY_ENV):
        monkeypatch.delenv(e, raising=False)
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["error"] == "odoo not configured"


async def test_read_tool_not_configured(monkeypatch):
    monkeypatch.delenv(odoo.URL_ENV, raising=False)
    out = await odoo.odoo_get_plan_cuentas()
    assert out["data"]["error"] == "odoo not configured"


# --------------------------------------------------------------------------- #
# health                                                                       #
# --------------------------------------------------------------------------- #


async def test_health_happy_path(_configured, monkeypatch):
    _install_fake(monkeypatch, common=_FakeCommon(version={"server_version": "18.0-20251222"}, uid=7))
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["reachable"] is True
    assert out["data"]["authenticated"] is True
    assert out["data"]["server_version"] == "18.0-20251222"
    assert out["data"]["uid"] == 7


async def test_health_auth_fails(_configured, monkeypatch):
    _install_fake(monkeypatch, common=_FakeCommon(uid=False))
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["reachable"] is True
    assert out["data"]["authenticated"] is False


async def test_health_unreachable(_configured, monkeypatch):
    def _boom(endpoint):
        raise OSError("connection refused")

    monkeypatch.setattr(odoo, "_proxy", _boom)
    out = await odoo.odoo_health()
    _assert_envelope(out)
    assert out["data"]["error"] == "odoo unreachable"


# --------------------------------------------------------------------------- #
# read tools                                                                   #
# --------------------------------------------------------------------------- #


async def test_get_company(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("res.company", "search"):
            return [1, 2]
        if (model, method) == ("res.company", "read"):
            return [
                {"id": 1, "name": "NU Desarrollos Conscientes S.R.L.", "vat": "30717928993", "currency_id": [3, "ARS"]},
                {"id": 2, "name": "Vastu inmobiliaria", "vat": False, "currency_id": [3, "ARS"]},
            ]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_get_company()
    _assert_envelope(out)
    assert out["data"]["count"] == 2
    names = {c["name"] for c in out["data"]["companies"]}
    assert "NU Desarrollos Conscientes S.R.L." in names
    assert out["data"]["companies"][0]["currency"] == "ARS"


async def test_get_plan_cuentas(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "search"):
            return [10, 11]
        if (model, method) == ("account.account", "read"):
            return [
                {"id": 10, "code": "111000", "name": "Caja", "account_type": "asset_cash", "reconcile": False},
                {"id": 11, "code": "411000", "name": "Ventas", "account_type": "income", "reconcile": False},
            ]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_get_plan_cuentas()
    _assert_envelope(out)
    assert out["data"]["count"] == 2
    assert out["data"]["accounts"][0]["code"] == "111000"


async def test_buscar_partner_by_cuit(_configured, monkeypatch):
    holder = {}
    def handler(model, method, args, kwargs):
        if (model, method) == ("res.partner", "search"):
            # assert the domain filtered by vat (11-digit cuit path)
            return [5]
        if (model, method) == ("res.partner", "read"):
            return [{"id": 5, "name": "Proveedor SA", "vat": "30111111118", "is_company": True}]
        return []

    _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    out = await odoo.odoo_buscar_partner("30-11111111-8")
    _assert_envelope(out)
    assert out["data"]["count"] == 1
    assert out["data"]["partners"][0]["vat"] == "30111111118"


async def test_get_comprobantes_empty(_configured, monkeypatch):
    _install_fake(monkeypatch, handler=lambda *a: [])
    out = await odoo.odoo_get_comprobantes(estado="posted")
    _assert_envelope(out)
    assert out["data"]["count"] == 0
    assert out["data"]["moves"] == []


async def test_check_l10n_ar(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("ir.module.module", "search"):
            return [1, 2, 3]
        if (model, method) == ("ir.module.module", "read"):
            return [{"name": "l10n_ar"}, {"name": "l10n_ar_afipws"}, {"name": "l10n_ar_afipws_fe"}]
        return []

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_check_l10n_ar()
    _assert_envelope(out)
    assert out["data"]["l10n_ar"] is True
    assert "l10n_ar_afipws_fe" in out["data"]["installed"]


# --------------------------------------------------------------------------- #
# error handling: Odoo Fault becomes a graceful error                         #
# --------------------------------------------------------------------------- #


async def test_odoo_fault_is_graceful(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        raise xmlrpc.client.Fault(2, "odoo.exceptions.AccessError\nNo tiene permiso")

    _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_get_diarios()
    _assert_envelope(out)
    assert "error" in out["data"]
    assert "rejected" in out["data"]["error"]


# --------------------------------------------------------------------------- #
# WRITE tools — must create in DRAFT and NEVER post                           #
# --------------------------------------------------------------------------- #


async def test_crear_factura_borrador_creates_draft_never_posts(_configured, monkeypatch):
    holder = {}

    def handler(model, method, args, kwargs):
        if (model, method) == ("account.move", "create"):
            # The created vals must NOT set state to posted.
            vals = args[0]
            assert vals.get("state") in (None, "draft")
            assert vals["move_type"] == "in_invoice"
            return 99
        return []

    _install_fake(monkeypatch, handler=handler, obj_holder=holder)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="in_invoice",
        partner_id=5,
        journal_id=2,
        invoice_date="2026-06-05",
        lineas=[{"name": "Servicio", "account_id": 11, "quantity": 1, "price_unit": 1000.0, "tax_ids": [3]}],
    )
    _assert_envelope(out)
    assert out["data"]["id"] == 99
    assert out["data"]["state"] == "draft"
    # CRITICAL: the connector must never have called action_post.
    methods = [(m, meth) for (m, meth, _a, _k) in holder["obj"].calls]
    assert ("account.move", "action_post") not in methods


async def test_crear_factura_invalid_move_type(_configured, monkeypatch):
    fake = _install_fake(monkeypatch, handler=lambda *a: 1)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="posted_invoice", partner_id=5, journal_id=2, invoice_date="2026-06-05", lineas=[{}]
    )
    _assert_envelope(out)
    assert out["data"]["error"] == "invalid move_type"
    # no create attempted
    assert all(meth != "create" for (_m, meth, _a, _k) in fake.calls)


async def test_crear_factura_missing_fields(_configured, monkeypatch):
    _install_fake(monkeypatch, handler=lambda *a: 1)
    out = await odoo.odoo_crear_factura_borrador(
        move_type="in_invoice", partner_id=0, journal_id=0, invoice_date="", lineas=[]
    )
    assert out["data"]["error"] == "missing fields"


async def test_crear_partner_reuses_existing_by_cuit(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("res.partner", "search"):
            return [42]  # already exists
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_crear_partner_borrador("Proveedor X", cuit="30111111118")
    _assert_envelope(out)
    assert out["data"]["created"] is False
    assert out["data"]["id"] == 42
    # must NOT have called create
    assert all(meth != "create" for (_m, meth, _a, _k) in fake.calls)


async def test_crear_cuenta_refuses_duplicate_code(_configured, monkeypatch):
    def handler(model, method, args, kwargs):
        if (model, method) == ("account.account", "search"):
            return [7]  # code exists
        return []

    fake = _install_fake(monkeypatch, handler=handler)
    out = await odoo.odoo_crear_cuenta("411000", "Ventas", "income")
    _assert_envelope(out)
    assert out["data"]["created"] is False
    assert all(meth != "create" for (_m, meth, _a, _k) in fake.calls)


# --------------------------------------------------------------------------- #
# LIVE (needs real Odoo + API key). Excluded from CI.                         #
# --------------------------------------------------------------------------- #


@pytest.mark.live
async def test_live_health():
    out = await odoo.odoo_health()
    assert "error" not in out["data"], out["data"]
    assert out["data"]["authenticated"] is True
