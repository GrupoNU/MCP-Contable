# Plugin: Registración y Estados Contables (Argentina — RT FACPCE)

Plugin de **MCP-Contable** para el área de **registración y estados contables**. Asiste a NU
Desarrollos (Responsable Inscripto) en consultas sobre asientos y partida doble, libros contables
obligatorios (Diario, Inventarios y Balances), y estados contables según las **Resoluciones Técnicas
(RT) de la FACPCE**, con **grounding** contra fuentes oficiales y **gates** de revisión profesional.

## Qué hace

- **Configura un perfil de trabajo** (rol, ente/CUIT, tamaño del ente, normas aplicables, cierre de
  ejercicio, libros, carpetas locales) vía entrevista de inicio (`cold-start-interview`), que
  personaliza el playbook del plugin.
- **Responde consultas de registración y estados contables** (`consulta-registracion`) aplicando el
  playbook y las reglas de grounding, **distinguiendo el marco conceptual estable** (partida doble,
  cómo se arma un asiento, qué rubros componen un estado) **de la cita normativa concreta** (qué RT
  lo regula, su número, objeto y vigencia), que **se verifica**.
- **Busca normativa contable** (`buscar-normativa-contable`) usando connectors oficiales para el
  **marco legal** y guiando la **verificación manual** de las RT:
  - `arca` → constancia/padrón de un CUIT (vía afip-ws de NU).
  - `ckan-juridico` / `ckan-nacional` → datasets; hallar el id de InfoLEG de una norma legal.
  - `infoleg` → recuperar el **CCyC (Ley 26.994)** y la **LGS (Ley 19.550)** por id.
  - `boletin-nacional` → normas del Boletín Oficial.
  - `santafe-sin` / `santafe-fiscal` → normativa/calendario de Santa Fe (uso marginal aquí).
- **Analiza una norma puntual** (`analizar-norma-contable`): recupera una norma legal por id/número y
  produce un resumen-borrador, o estructura el análisis de una RT que se debe verificar contra FACPCE.

### Áreas cubiertas (marco conceptual estable + cita normativa verificada)

- **Partida doble, plan de cuentas y asientos** — marco conceptual estable, se explica.
- **Libros contables obligatorios** (Diario, Inventarios y Balances) — marco del **CCyC (Ley 26.994)**
  y la **LGS (Ley 19.550)**; rúbrica.
- **Estados contables básicos** (Situación Patrimonial, Resultados, Evolución del PN, Flujo de
  Efectivo) — qué son (marco) + exposición normada por **RT 8 / RT 9** (cita verificada).
- **Resoluciones Técnicas de la FACPCE** — RT 6 (ajuste por inflación), RT 8 (presentación), RT 9
  (rubros), RT 16 (marco conceptual), RT 17 (medición), RT 41/42 (entes pequeños/medianos) —
  **número, objeto y vigencia siempre verificados** contra FACPCE.
- **Ajuste por inflación (RT 6)** — el mecanismo se explica; el **coeficiente / índice (IPIM/IPC) se
  verifica**, nunca se inventa.

## Qué NO hace

- **No da asesoramiento contable.** Toda salida es un **borrador para revisión de un contador
  matriculado**, que verifica el encuadre normativo y las cifras y asume la responsabilidad.
- **No afirma el número, el objeto ni la vigencia de una RT de memoria** como verdad fija: la cita de
  una RT se **verifica manualmente contra `facpce.org.ar`** (las RT **no tienen connector**) y se
  marca `[verify]` si no hay fuente reciente.
- **No da un coeficiente de ajuste por inflación ni un índice de memoria** (RT 6): se verifican.
- **No presenta un proyecto/borrador de RT como norma vigente** sin confirmar su aprobación y la
  adopción provincial.
- **No registra un asiento de cierre, no emite estados contables para presentación ni cierra el
  ejercicio**: esas acciones requieren confirmación del usuario y revisión profesional.

## Skills

| Skill | Invocación | Qué hace |
|---|---|---|
| `cold-start-interview` | `/registracion-estados-contables:cold-start-interview` | Entrevista de configuración del perfil. |
| `consulta-registracion` | `/registracion-estados-contables:consulta-registracion` | Responde una consulta de registración o estados contables. |
| `buscar-normativa-contable` | `/registracion-estados-contables:buscar-normativa-contable` | Busca normativa legal con los connectors y guía la verificación de RT contra FACPCE. |
| `analizar-norma-contable` | `/registracion-estados-contables:analizar-norma-contable` | Recupera y resume una norma legal por id/número, o estructura el análisis de una RT a verificar. |

## Connectors (MCP) — ver `.mcp.json`

Se ejecutan por stdio con `uv run --directory <connectors>`. Las rutas en `.mcp.json` son
**absolutas a la carpeta `connectors` de este repo en esta máquina** — ajustarlas si la instalación
difiere (lección de MCP-Juridico). El connector `arca` requiere `AFIP_WS_BASE_URL` configurado
(afip-ws de NU, accesible por Tailscale).

> **Nota honesta:** las **RT de la FACPCE no tienen connector** (no hay API; son PDFs sueltos, un
> recurso estático/futuro con fecha de corte). Su cita se **verifica manualmente contra
> `facpce.org.ar`** y, cuando corresponda, contra la resolución del CPCE provincial que la adopta.
> Los connectors cubren el marco legal (CCyC, LGS) vía `infoleg`, no las RT.

## Configuración persistida

El perfil personalizado se guarda en:
`~/.claude/plugins/config/mcp-contable/registracion-estados-contables/CLAUDE.md`

## Aviso

Herramienta de asistencia. **No reemplaza el criterio de un contador público matriculado.** Toda
salida es un borrador sujeto a revisión profesional. Autor: **Grupo NU**.
