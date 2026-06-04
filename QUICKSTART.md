# Quickstart — MCP-Contable

> Guía para desarrolladores del proyecto. (La guía de instalación para el usuario contable se
> escribirá cuando haya plugins, en Fase 2.)

## Requisitos

- **Python 3.12**
- **uv** (gestor de paquetes/venv) — https://docs.astral.sh/uv/
- Git

## Setup del entorno de desarrollo

```bash
git clone https://github.com/GrupoNU/MCP-Contable.git
cd MCP-Contable/connectors
uv sync                       # crea .venv e instala deps (incl. dev)
```

## Correr los tests

```bash
cd connectors
uv run pytest -m "not live"   # tests sin pegar a APIs reales (lo normal / CI)
uv run pytest                 # incluye tests @live (pegan a fuentes reales)
uv run pytest -v              # verboso
```

En Windows, si aparece un warning del venv global, prefijá `VIRTUAL_ENV=`:

```bash
VIRTUAL_ENV= uv run pytest -m live -v
```

## Estructura del código

- `src/mcp_contable/common/` — fundaciones compartidas (NO duplicar lógica acá):
  - `http.py` — `fetch()`, único camino HTTP. Zero-retention (no loguea bodies).
  - `grounding.py` — `ground()`, `SourceTier`, `to_dict()`. Sistema anti-alucinación.
  - `cache.py` — `TTLCache`, `cached_call()`.
- `src/mcp_contable/<fuente>/server.py` — un server FastMCP por fuente (Fase 1+).

## Convenciones

- Código **en inglés**; contenido contable (plugins/skills) **en español**.
- Toda tool de connector devuelve resultados envueltos por `ground()` / `to_dict()`.
- Todo HTTP pasa por `common.http.fetch()` (nunca httpx directo).
- Commits: `tipo(scope): descripción` (feat|fix|docs|refactor|chore|test).
- **No `git push` sin confirmación.**

## Correr un connector (Fase 1+)

```bash
uv run python -m mcp_contable.ckan_nacional.server   # smoke test stdio
```

## Reglas del equipo

Ver [CLAUDE.md](CLAUDE.md) (raíz), [connectors/CLAUDE.md](connectors/CLAUDE.md) y
[plugins/CLAUDE.md](plugins/CLAUDE.md).
