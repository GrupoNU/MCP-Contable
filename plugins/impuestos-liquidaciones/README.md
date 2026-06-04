# Plugin: Impuestos y Liquidaciones (Argentina — Nación + Santa Fe)

Plugin de referencia de **MCP-Contable** para el área de **impuestos y liquidaciones**. Asiste a
NU Desarrollos (Responsable Inscripto) en consultas sobre IVA, Ganancias, Ingresos Brutos de Santa
Fe, monotributo, Bienes Personales y retenciones/percepciones, con **grounding** contra fuentes
oficiales y **gates** de revisión profesional.

## Qué hace

- **Configura un perfil de trabajo** (rol, entidad/CUIT, régimen, jurisdicciones, carpetas locales)
  vía entrevista de inicio (`cold-start-interview`), que personaliza el playbook del plugin.
- **Responde consultas impositivas generales** (`consulta-impuestos`) aplicando el playbook y las
  reglas de grounding.
- **Busca normativa fiscal** (`buscar-normativa-fiscal`) usando connectors oficiales:
  - `arca` → constancia/padrón de un CUIT (vía afip-ws de NU).
  - `ckan-juridico` / `ckan-nacional` → datasets; hallar el id de InfoLEG de una norma fiscal.
  - `infoleg` → recuperar una norma nacional por id.
  - `boletin-nacional` → RG de ARCA y otras normas del Boletín.
  - `santafe-sin` → normativa fiscal de Santa Fe (Código Fiscal Ley 3456).
  - `santafe-fiscal` → calendario impositivo de Santa Fe (URL oficial por año).
- **Analiza una norma puntual** (`analizar-norma-fiscal`): la recupera por id/número y produce un
  resumen-borrador.

### Áreas cubiertas (con grounding obligatorio)

- IVA (Ley 23.349), Ganancias (Ley 20.628), Ingresos Brutos Santa Fe (Código Fiscal Ley 3456).
- Monotributo (Ley 24.977) — **categorías/topes/cuotas siempre verificados** (se actualizan por IPC).
- Bienes Personales (Ley 23.966) y reformas 2024-2026 (Ley 27.743, REIBP, blanqueo) — distinguiendo
  vigente de proyecto.
- Retenciones y percepciones (RG de ARCA) — **alícuotas siempre verificadas** (cambian por RG).

## Qué NO hace

- **No da asesoramiento contable ni impositivo.** Toda salida es un **borrador para revisión de un
  contador matriculado**, que verifica las cifras y asume la responsabilidad.
- **No afirma alícuotas, topes, mínimos, categorías ni vencimientos** sin un resultado de connector
  con `retrieved_at`. Sin fuente → `[verify]`.
- **No transcribe una tabla de monotributo de memoria** (cambia semestralmente por IPC).
- **No presenta una reforma/proyecto como vigente** sin verificar su entrada en vigor.
- **No presenta DDJJ, genera F.931 ni recategoriza**: esas acciones requieren confirmación del
  usuario y revisión profesional.

## Skills

| Skill | Invocación | Qué hace |
|---|---|---|
| `cold-start-interview` | `/impuestos-liquidaciones:cold-start-interview` | Entrevista de configuración del perfil. |
| `consulta-impuestos` | `/impuestos-liquidaciones:consulta-impuestos` | Responde una consulta impositiva general. |
| `buscar-normativa-fiscal` | `/impuestos-liquidaciones:buscar-normativa-fiscal` | Busca normativa/RG/calendario con los connectors. |
| `analizar-norma-fiscal` | `/impuestos-liquidaciones:analizar-norma-fiscal` | Recupera y resume una norma por id/número. |

## Connectors (MCP) — ver `.mcp.json`

Se ejecutan por stdio con `uv run --directory <connectors>`. Las rutas en `.mcp.json` son
**absolutas a la carpeta `connectors` de este repo en esta máquina** — ajustarlas si la instalación
difiere (lección de MCP-Juridico). El connector `arca` requiere `AFIP_WS_BASE_URL` configurado
(afip-ws de NU, accesible por Tailscale).

## Configuración persistida

El perfil personalizado se guarda en:
`~/.claude/plugins/config/mcp-contable/impuestos-liquidaciones/CLAUDE.md`

## Aviso

Herramienta de asistencia. **No reemplaza el criterio de un contador público matriculado.** Toda
salida es un borrador sujeto a revisión profesional. Autor: **Grupo NU**.
