# Plugin: Estudio Contable (puerta única / recepción)

La **recepción** del estudio contable de NU Desarrollos. Es el punto de entrada único: recibe una
consulta contable/impositiva en lenguaje natural, la **clasifica** por área y la **deriva** al
plugin especialista correcto. No resuelve consultas de fondo: orquesta y deriva.

## Qué hace

- **Configura el perfil global del estudio** (`cold-start-interview`): rol, entidad/CUIT, régimen,
  jurisdicciones, carpetas locales — **una sola vez**. Las áreas lo leen antes que su propio perfil.
- **Recibe y deriva consultas** (`recepcion`): clasifica la consulta por área y deriva al skill de
  entrada correspondiente. Si la consulta cruza varias áreas, la descompone en pasos ordenados.

## A dónde deriva

| Si la consulta es de… | Deriva a |
|---|---|
| IVA, Ganancias, IIBB, monotributo, retenciones/percepciones | `impuestos-liquidaciones` |
| nómina, cargas sociales, F.931, ART | `sueldos` |
| asientos, libros, balance, estados contables, RT FACPCE | `registracion-estados-contables` |
| vencimientos ARCA, regímenes de información, IGJ/RPJEC, inscripciones | `societario-cumplimiento` |

## Qué NO hace

- **No produce contenido fiscal/contable sustantivo:** no da alícuotas, asientos, liquidaciones ni
  vencimientos. Eso lo hacen las áreas (con su propio grounding).
- **No cita normativa:** deriva al área que sí lo hace.
- **No usa connectors propios** (su `.mcp.json` está vacío).
- **No es asesoramiento contable:** la derivación es el primer paso de un trabajo que revisa un
  contador matriculado.

## Skills

| Skill | Invocación | Qué hace |
|---|---|---|
| `cold-start-interview` | `/estudio-contable:cold-start-interview` | Configura el perfil global del estudio. |
| `recepcion` | `/estudio-contable:recepcion` | Clasifica una consulta y deriva al área correcta. |

## Configuración persistida

El perfil global se guarda en:
`~/.claude/plugins/config/mcp-contable/estudio-contable/CLAUDE.md`
(las áreas lo leen antes que su propio perfil).

## Aviso

Herramienta de asistencia. **No reemplaza el criterio de un contador público matriculado.** Toda
salida del estudio es un borrador sujeto a revisión profesional. Autor: **Grupo NU**.
