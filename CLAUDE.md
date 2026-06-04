# CONTEXTO DE DESARROLLO — NO es contenido de producto

> ⚠️ Este archivo son **instrucciones para el equipo de agentes que PROGRAMA** MCP-Contable.
> NO confundir con los `CLAUDE.md` de **producto** que viven dentro de cada plugin
> (`plugins/<area>/CLAUDE.md`), que son el playbook contable que lee Claude Cowork.
> Ver `plugins/CLAUDE.md` para la regla de separación completa.

---

## Qué es este proyecto

**MCP-Contable** = "Claude for Legal, versión contable argentina". Un estudio contable de
agentes IA para uso propio de **NU Desarrollos** (Diego revisa; un contador matriculado valida
antes de uso real), extensible a producto. Es el **gemelo contable de MCP-Jurídico**
(`D:\git\MCP-Juridico`), del que se calca la arquitectura y el método (probados).

Arquitectura (calcada del repo oficial verificado `anthropics/claude-for-legal`):
- **Marketplace local de plugins** contables en Markdown (`plugins/`).
- **Connectors MCP en Python** (FastMCP, stdio) a fuentes fiscales/contables argentinas (`connectors/`).
- El 90% del valor es **conocimiento contable en Markdown**; el código Python es **solo la
  capa de connectors a datos**.

Despliegue: **Claude Cowork / Claude Code**. El motor de IA es la suscripción Claude del propio
usuario (costo IA $0). Accede a carpetas locales de NU + connectors MCP.

Plan completo: ver `docs/ARCHITECTURE.md` y el plan en `.claude/plans/`.

## Idioma (regla híbrida)

- **Código Python en inglés**: nombres de módulos, funciones, variables, tools MCP, tests.
- **Contenido contable en español**: plugins, skills (`SKILL.md`), CLAUDE.md de producto,
  docs de dominio. Es contenido para contadores argentinos.
- **Comunicación con el usuario (Diego): español.**
- **Commits en inglés**, formato `tipo(scope): descripción` (feat|fix|docs|refactor|chore|test).

## Stack y herramientas

- **Python 3.12** · gestor **uv** (no pip directo). Venv aislado en `connectors/.venv`.
- **FastMCP** para los servers MCP, transporte **stdio** (local, sin endpoints expuestos).
- **httpx** para HTTP, **selectolax** para scraping, **pytest + respx** para tests.
- Un server FastMCP **por fuente** de datos (no monolito): aísla fallos, se testea por separado.

## Reglas de ingeniería (estándar Grupo NU)

- **Testing obligatorio**: nunca se integra código sin test verde. Bug fix = test primero.
  Cada tool MCP tiene tests: happy path, fuente caída (timeout→error grácil), payload vacío,
  y assert de que `source_tier` + `retrieved_at` vienen poblados.
- **Cambios pequeños e incrementales** sobre cambios masivos.
- **NUNCA hacer `git push`** sin confirmación de Diego. NUNCA force push a main.
- **Confirmar antes de cambios destructivos.** Explicar antes de hacer.
- **Commits atómicos** (un cambio lógico por commit).
- Mantener **docs actualizados** cuando se cambia código/config.

## Grounding anti-alucinación (INNEGOCIABLE — más crítico que en legal)

En contable hay **MONTOS, ALÍCUOTAS, TOPES, VENCIMIENTOS y CATEGORÍAS** que cambian
constantemente (a veces mensual/semestral). Toda tool de connector devuelve
`{data, source_tier, source_url, retrieved_at}`:
- **Tier A** — API oficial estructurada (ARCA vía afip-ws, datos.gob.ar / datos.jus.gob.ar CKAN) → cita usable.
- **Tier B** — scraping de fuente oficial predecible (InfoLEG, Boletín, SIN SF) → marca
  `[scraped — verificar contra fuente oficial]`.
- **Tier C** — sin connector / conocimiento del modelo → marca `[verify]` obligatoria.

Lógica central en `connectors/src/mcp_contable/common/grounding.py`. **Toda salida es un
borrador para revisión de un contador matriculado.** Nunca afirmar un monto/alícuota/categoría/
vencimiento sin `retrieved_at` reciente. Distinguir **proyecto** de **norma vigente**.

## Confidencialidad / zero-retention

- `common/http.py` **NUNCA loguea request/response bodies** (ni params, headers, ni URL completa).
- Los `logs/` de los plugins registran **solo metadata** (tool, timestamp, source_tier) —
  nunca contenido contable de NU.
- Sin telemetría saliente. Detalles en `docs/SECURITY.md`.
- **Credenciales (certificado ARCA, claves):** viven fuera del repo. El connector `arca` NO
  maneja el certificado: reusa el microservicio `afip-ws` del VPS por HTTP (ver `docs/ARCHITECTURE.md`).

## Cómo trabaja el equipo

Diego es Director. Claude (orquestador) es Tech Lead — coordina agentes, **no codea
directo lo que puede delegar**. Los agentes implementan dentro de su scope.
- Paralelismo **conservador**: fundaciones primero (validadas), luego equipos en paralelo.
- Checkpoints **por fase**.
- Validación contable: **agente verifica cifras/normas contra fuentes + Diego/contador final**.

## Comandos útiles

```bash
cd connectors
uv sync                       # instalar deps
uv run pytest -m "not live"   # tests sin pegar a APIs reales (CI)
uv run pytest                 # incluye tests @live
uv run python -m mcp_contable.ckan_nacional.server   # correr un server (smoke stdio)
```
