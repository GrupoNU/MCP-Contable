# Session Log — MCP-Contable

> Bitácora de avance por fases. Lo más reciente arriba.

## 2026-06-04 — Fase 0: Fundaciones

**Estado:** completada (pendiente checkpoint de Diego antes de Fase 1).

### Encuadre cerrado con el usuario
- Despliegue: **Claude Cowork** (gemelo del jurídico, no es servicio web).
- Jurisdicción: **Nación (ARCA) + Santa Fe (IIBB, RPJEC)**.
- Perfil NU: **Responsable Inscripto** (IVA + Ganancias).
- Validador: **Diego revisa** (sin matrícula) → encabezado conservador por defecto.
- Área piloto: **impuestos-liquidaciones**, luego replicar a las otras 3.
- Managed-agents: incluir **vencimientos ARCA** desde temprano.
- **5 plugins:** estudio-contable (puerta única) + 4 áreas.

### Investigación de fuentes (verificada de primera mano)
- **ARCA:** sin API pública sin certificado. PERO NU tiene el microservicio **afip-ws** en su VPS
  (cert. de NU, mismo que Odoo, WS `ws_sr_constancia_inscripcion`) → connector `arca` = cliente
  HTTP del afip-ws (Tier A). Plomería Tailscale pendiente (Fase 1).
- **datos.gob.ar** CKAN: Tier A ✅. **datos.jus.gob.ar** CKAN: Tier A ✅ (ids de normas fiscales).
- **InfoLEG** / **Boletín** / **Santa Fe SIN** / **calendario SF**: Tier B (scraping).
- **datos.santafe** CKAN: vacío, no usar. **API SF / RPJEC / DDJJ**: bloqueadas (login).
- **Monotributo / calendario ARCA / RT FACPCE:** recursos estáticos con fecha de corte + `[verify]`.

### Hecho en Fase 0
- Scaffolding: `.gitignore`, `.gitattributes`, `LICENSE`, `README.md`, `QUICKSTART.md`.
- `.claude/settings.json` (deny push/.env/certs; allow uv/pytest/git + WebFetch dominios fiscales).
- 3 CLAUDE.md de **desarrollo** (raíz, connectors, plugins).
- `common/` copiado de Legal → renombrado `mcp_contable` (http/grounding/cache).
- `pyproject.toml` + `.env.example` + `uv sync` (fastmcp, httpx, selectolax, pytest, respx).
- Tests de `common/` adaptados → **36 verdes** (`pytest -m "not live"`).
- Docs base: ARCHITECTURE, GROUNDING, SECURITY, SOURCES, SESSION_LOG.
- `marketplace.json` con los 5 plugins declarados.

### Gate Fase 0
- ✅ `pytest -m "not live"` verde (36).
- ✅ Ningún dato de NU en el repo; credenciales/certs ignorados.
- ⏸️ Checkpoint con Diego antes de Fase 1.

### Próximo (Fase 1)
- Sub-paso 1.0: exponer afip-ws a Tailscale + verificar (`GET /health`).
- Connectors en orden: ckan_nacional → arca → ckan_juridico → infoleg → boletin_nacional →
  santafe_sin → santafe_fiscal. Tests por connector.
