# MCP-Contable

> **Estudio contable de agentes IA para la gestión contable/impositiva argentina** — uso propio
> de **NU Desarrollos**, replicando el molde probado de su gemelo **MCP-Jurídico** (que a su vez
> calca el patrón oficial de *Claude for Legal* de Anthropic).

MCP-Contable es un **marketplace local de plugins contables** (en Markdown, español) +
**connectors MCP en Python** (FastMCP, stdio) a fuentes fiscales/contables argentinas. Corre
en **Claude Cowork / Claude Code** usando la suscripción Claude del propio usuario (costo IA
$0). Claude accede a las **carpetas locales** de NU Desarrollos (facturas, papeles de trabajo,
DDJJ) + las fuentes oficiales vía los connectors.

## Arquitectura

- **`plugins/`** — el "estudio": un plugin por especialidad contable (Markdown). Cada plugin
  tiene su **playbook** (`CLAUDE.md` de producto = el "cerebro" del área) + skills.
  - `estudio-contable` — **puerta única / recepción**: clasifica la consulta y deriva al área.
  - `impuestos-liquidaciones` — IVA, Ganancias, IIBB, monotributo, retenciones/percepciones.
  - `sueldos` — nómina, cargas sociales, F.931, ART.
  - `registracion-estados-contables` — asientos, libros, balance, RT FACPCE.
  - `societario-cumplimiento` — vencimientos ARCA, regímenes de información, IGJ/RPJEC.
- **`connectors/`** — servers FastMCP (Python, código en inglés) a fuentes oficiales: ARCA
  (vía microservicio afip-ws), datos.gob.ar / datos.jus.gob.ar (CKAN), InfoLEG, Boletín
  Oficial, Santa Fe (SIN, calendario fiscal).
- **`recursos/`** — estáticos versionados con **fecha de corte** (tabla de monotributo,
  calendario ARCA, mapa de RT FACPCE), siempre marcados `[verify]`.
- **`managed-agents/`** — agentes recurrentes (ej. alertas de vencimientos ARCA).
- **`docs/`** — ARCHITECTURE, GROUNDING, SECURITY, SOURCES, SESSION_LOG.

## Grounding anti-alucinación (innegociable)

En contable el riesgo nº1 es presentar un **monto/alícuota/tope/vencimiento desactualizado**
como vigente. Por eso:

- Toda tool de connector devuelve `{data, source_tier, source_url, retrieved_at}`.
- **Tier A** (API oficial: ARCA/afip-ws, CKAN) → cita usable.
- **Tier B** (scraping oficial: InfoLEG, Boletín, SIN SF) → `[scraped — verificar contra fuente oficial]`.
- **Tier C** (sin connector / memoria del modelo) → `[verify]` obligatorio.
- **Nunca** se afirma una cifra/alícuota/categoría/vencimiento sin `retrieved_at` reciente.
- **Toda salida es un borrador para revisión de un contador matriculado.**

## Estado

🚧 En construcción. Ver `docs/SESSION_LOG.md` para el avance por fases.

## Aviso

Herramienta de asistencia. **No reemplaza el criterio de un contador público matriculado.**
Toda salida es un borrador sujeto a revisión profesional. Autor: **Grupo NU**.
