# CONTEXTO DE DESARROLLO (área: connectors) — NO es contenido de producto

> ⚠️ Instrucciones para programar los **connectors MCP en Python**.
> Hereda del `CLAUDE.md` de la raíz. Acá van las convenciones específicas de esta capa.

---

## Qué vive acá

Los **servers FastMCP** que conectan Claude a las fuentes de datos fiscales/contables
argentinas. Cada fuente = un módulo propio bajo `src/mcp_contable/<fuente>/server.py`.

Fuentes previstas (orden de construcción):
1. `ckan_nacional` — datos.gob.ar (API CKAN real, **Tier A**) — reference connector
2. `arca` — Constancia/Padrón AFIP vía microservicio afip-ws de NU (HTTP, **Tier A**)
3. `ckan_juridico` — datos.jus.gob.ar (API CKAN, **Tier A**) — ids de normas fiscales
4. `infoleg` — InfoLEG (scraper, Tier B) — norma por id
5. `boletin_nacional` — Boletín Oficial Nacional (scraper, Tier B) — RG ARCA
6. `santafe_sin` — Sistema de Información Normativa SF (scraper, Tier B)
7. `santafe_fiscal` — calendario impositivo / IIBB Santa Fe (scraper, Tier B)

## Estructura de un connector

```
src/mcp_contable/
├─ common/                  # COMPARTIDO por todos — no duplicar lógica acá
│  ├─ http.py               # cliente httpx (retry, timeout, NO loguea bodies)
│  ├─ grounding.py          # tiers de fuente + envoltura de respuesta
│  └─ cache.py              # cache local con TTL
└─ <fuente>/
   ├─ __init__.py
   └─ server.py             # FastMCP server: define las tools de esta fuente
```

## Convenciones de código

- **Inglés** para todo el código (módulos, funciones, tools, variables, tests).
- Cada **tool MCP** se nombra `<fuente>_<accion>` (ej. `ckan_search_datasets`, `arca_get_constancia`,
  `infoleg_get_norma`, `santafe_fiscal_get_calendario`).
- Toda tool **devuelve la respuesta envuelta** por `common/grounding.py` → incluye
  `source_tier`, `source_url`, `retrieved_at`. Nunca devolver data cruda sin envolver.
- Todo HTTP pasa por `common/http.py`. **Prohibido** instanciar httpx directo en un server
  (rompería la garantía de zero-retention).
- Errores de fuente (timeout, 5xx, payload vacío) se manejan **grácilmente**: la tool
  devuelve un resultado con error explicado, nunca explota.

## El connector `arca` (caso especial — no maneja credenciales)

- NO porta WSAA ni toca el certificado de AFIP. Es un **cliente HTTP fino del microservicio
  `afip-ws`** que ya corre en el VPS de NU (cert. de NU, mismo que Odoo).
- Pega a `GET /fiscal/cuit/{cuit}` y `GET /health` del afip-ws (URL base configurable por `.env`,
  host Tailscale del VPS). Envuelve la respuesta con `ground(..., SourceTier.A, ...)`.
- Si el afip-ws está caído/inalcanzable → error grácil explicado (nunca inventa datos de padrón).

## Testing (obligatorio, regla Grupo NU)

- `pytest + respx`. Mocks de httpx con **cassettes** (respuestas reales grabadas) en
  `tests/cassettes/`.
- Cobertura mínima por tool: happy path · timeout/5xx · payload vacío · assert de
  `source_tier` + `retrieved_at` poblados.
- Tests que pegan a la API real → marcados `@pytest.mark.live`, **excluidos de CI**
  (`pytest -m "not live"`).
- **Ningún connector se integra sin sus tests verdes.**

## Comandos

```bash
uv sync
uv run pytest tests/test_<fuente>.py
uv run python -m mcp_contable.<fuente>.server   # smoke test del server
```
