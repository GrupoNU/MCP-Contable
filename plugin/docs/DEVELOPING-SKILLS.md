# CONTEXTO DE DESARROLLO (área: plugins) — NO es contenido de producto

> ⚠️ **LEER PRIMERO — Regla de separación de CLAUDE.md (crítica):**
>
> Este archivo (`plugins/CLAUDE.md`) son instrucciones para **escribir** los plugins
> contables. Es de **DESARROLLO**.
>
> Los `CLAUDE.md` que viven **DENTRO** de cada plugin (`plugins/<area>/CLAUDE.md`) son
> de **PRODUCTO**: el playbook contable que Claude Cowork lee como cerebro del plugin.
> Esos **NO** son instrucciones de desarrollo y NUNCA deben contener convenciones de código.
>
> | Ubicación | Tipo | Header que lleva |
> |---|---|---|
> | `plugins/CLAUDE.md` (este) | DESARROLLO | `# CONTEXTO DE DESARROLLO` |
> | `plugins/<area>/CLAUDE.md` | PRODUCTO | `# PLAYBOOK CONTABLE` |
>
> **Regla de oro:** el de desarrollo nunca baja a un plugin concreto; el de producto
> nunca sube a este nivel. No mezclar.

---

## Los plugins del estudio

- **`estudio-contable`** — puerta única / recepción-socio. **Liviano** (sin connectors propios,
  sin playbook de dominio pesado): clasifica la consulta y deriva al área correcta. Skills:
  `recepcion` (triage→derivación) y `cold-start-interview` global (perfil de NU una sola vez).
- **`impuestos-liquidaciones`** — IVA, Ganancias, IIBB, monotributo, retenciones/percepciones. (Área de referencia.)
- **`sueldos`** — nómina, cargas sociales, F.931, ART.
- **`registracion-estados-contables`** — asientos, libros, balance, RT FACPCE.
- **`societario-cumplimiento`** — vencimientos ARCA, regímenes de información, IGJ/RPJEC.

## Cómo se estructura un plugin de área (patrón verificado de Claude for Legal)

```
plugins/<area>/
├─ .claude-plugin/
│  └─ plugin.json          # name, version, description, author
├─ .mcp.json               # declara qué connectors MCP usa (rutas ABSOLUTAS a connectors/)
├─ CLAUDE.md               # 🧮 PLAYBOOK CONTABLE (producto) — posiciones del área
├─ README.md               # qué hace el plugin, qué NO hace
├─ skills/
│  ├─ cold-start-interview/SKILL.md   # el "setup interview" del área
│  └─ <skill>/SKILL.md                # un skill = una carpeta con SKILL.md
├─ agents/                 # subagentes (opcional)
├─ hooks/                  # lógica pre/post (opcional)
└─ logs/                   # metadata de runtime (NUNCA contenido contable de NU)
```

El plugin `estudio-contable` es más liviano: `.mcp.json` mínimo o ausente (no usa connectors
propios), y su `CLAUDE.md` de producto define el **mapa de áreas** y las reglas de derivación,
no posiciones de dominio.

## Anatomía de un SKILL.md (patrón verificado)

```markdown
---
name: nombre-en-kebab-case
description: >
  Qué hace y cuándo se usa. Si lo carga otro skill, indicarlo.
user-invocable: true        # true = invocable con /<plugin>:<skill>
---

# Título del Skill

## Propósito
[Qué resuelve, en 1-2 líneas]

## [Procedimiento paso a paso]
[El skill define el PROCEDIMIENTO. Los valores concretos (alícuotas, topes,
 vencimientos, categorías) se leen del CLAUDE.md de producto o se obtienen por
 connector — NUNCA se hardcodean en el skill.]

## Grounding
[Reglas de cita: Tier A/B usable con fuente, Tier C → [verify].
 Toda salida es borrador para revisión de un contador matriculado.]

## Qué este skill NO hace
[Límites explícitos. Gates de "no proceder sin revisión profesional".]
```

## Principios de diseño (calcados de Claude for Legal)

1. **Separación procedimiento/posiciones**: el SKILL.md dice *cómo* hacer la tarea; el
   `CLAUDE.md` de producto dice *cuáles son las posiciones contables* (configurables por el
   cold-start-interview). **Nunca hardcodear montos/alícuotas/vencimientos en el skill.**
2. **Grounding estricto**: sin fuente conectada (Tier A/B), toda cifra/cita lleva `[verify]`.
3. **Gates de consecuencias**: acciones con efecto (presentar DDJJ, generar F.931, registrar
   asiento de cierre) requieren confirmación y recordatorio de revisión profesional.
4. **Sección "Qué NO hace"** obligatoria en cada skill.
5. **Distinguir proyecto de norma vigente** (trampa específica de lo fiscal argentino).

## Idioma

Todo el contenido de plugins/skills es **en español** (es contenido contable argentino).
Solo el nombre técnico de archivos/carpetas va en kebab-case (ej. `cold-start-interview`).

## Validación

Cada área se da por "lista" solo cuando: (a) sus skills cargan en Claude Code, (b) el
cold-start-interview persiste el perfil, (c) el **agente validador verificó las cifras/normas
contra fuentes oficiales**, y (d) queda marcada para revisión de **Diego / un contador
matriculado** antes de uso real.
