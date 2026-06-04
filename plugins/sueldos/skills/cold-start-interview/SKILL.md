---
name: cold-start-interview
description: >
  Entrevista de configuración inicial del plugin sueldos. Detecta si el perfil ya está configurado;
  si no, entrevista al usuario (rol, entidad/CUIT empleador, régimen, jurisdicciones, convenio
  colectivo, ART, dotación, carpetas locales) y escribe el perfil personalizado que reemplaza los
  [PLACEHOLDER] del playbook. Usar al instalar el plugin o cuando el usuario pida reconfigurar.
  Tiene versión quick (~2 min) y full.
user-invocable: true
---

# Cold Start — Entrevista de configuración (sueldos y nómina)

## Propósito

Personalizar el plugin antes del primer uso real: capturar **rol del usuario**, **entidad/CUIT del
empleador**, **régimen fiscal**, **jurisdicciones**, **convenio colectivo aplicable**, **ART**,
**dotación** y **carpetas locales de trabajo**, y persistir un perfil que reemplaza los
`[PLACEHOLDER]` del playbook (`CLAUDE.md` del plugin). El perfil ajusta el encabezado de
work-product, los gates y qué prioriza el área.

## Paso 0 — Detectar si ya está configurado

1. Si existe un **perfil global del estudio**
   (`~/.claude/plugins/config/mcp-contable/estudio-contable/CLAUDE.md`), leerlo primero: puede
   tener ya el rol, la entidad y las jurisdicciones. Reusar eso y preguntar solo lo que falte.
2. Leé el perfil del área en
   `~/.claude/plugins/config/mcp-contable/sueldos/CLAUDE.md` si existe; si no, leé la plantilla del
   plugin (`CLAUDE.md`).
3. Buscá marcadores `[PLACEHOLDER` en la sección 1 (Perfil).
   - **Sin placeholders** → ya está configurado. Mostrá un resumen y preguntá si quiere
     **(a)** mantenerlo, **(b)** editar un campo, o **(c)** reconfigurar. No sobrescribas sin confirmar.
   - **Con placeholders** → continuá con la entrevista.
4. Preguntá si quiere la versión **quick** (~2 min) o **full**.

## Paso 1 — Entrevista (preguntá de a una, en prosa, conversacional)

**Quick (mínimo imprescindible):**

1. **Rol.** "¿Sos contador/a matriculado/a, o un usuario con/sin acceso a un contador que revise el
   trabajo?" → Mapear a `contador matriculado` | `usuario con acceso a contador` |
   `usuario sin acceso a contador`. (Default conservador si no contesta: sin acceso.)
2. **Entidad y CUIT del empleador.** "¿Para qué entidad empleadora trabajamos (razón social) y cuál
   es su CUIT?" Si da un CUIT, podés ofrecer verificar la constancia con `arca_get_constancia` (no es
   obligatorio).
3. **Régimen fiscal del empleador.** "¿La entidad es **Responsable Inscripto** o **Monotributo**?"
   (Default del plugin: Responsable Inscripto.)
4. **Convenio colectivo (CCT).** "¿Bajo qué **convenio colectivo** está el personal (número y
   nombre), o están **fuera de convenio**?" Esto define las escalas salariales (que siempre se
   verifican).

**Full (además de lo anterior):**

5. **Jurisdicciones.** "¿La sede laboral es en **Santa Fe**? ¿Hay personal en otras provincias?"
6. **ART.** "¿Con qué **aseguradora de riesgos del trabajo (ART)** tienen contrato?" → Guardar el
   nombre; la **alícuota la fija la ART** y no se afirma de memoria.
7. **Dotación / modalidad.** "¿Cuántos empleados, qué jornada (completa/parcial), hay eventuales o
   contratos especiales?"
8. **Carpetas locales.** "¿Dónde están las carpetas de trabajo (recibos, legajos, liquidaciones,
   F.931) que querés que el sistema pueda consultar?" → Guardar la **ruta** en el perfil. **Nunca
   copiar el contenido al perfil ni al repo** (zero-retention).
9. **Criterios del estudio (opcional).** Preferencias de presentación, criterios propios.

## Paso 2 — Verificar hechos laborales/previsionales que afirme el usuario

Si el usuario afirma un dato verificable (p. ej. "la alícuota de contribuciones es del X%", "el tope
de la base imponible es $...", "el básico del convenio subió a $...", "tal asignación familiar es
$..."), **no lo des por cierto**: marcalo como **a verificar** y ofrecé recuperarlo con
`buscar-normativa-laboral` / `analizar-norma-laboral` o contra ARCA. No incorpores cifras al perfil
sin verificar; el perfil guarda **convenio, ART y estructura, no montos**.

## Paso 3 — Escribir el perfil

1. Tomá la **plantilla** (`CLAUDE.md` del plugin), reemplazá los `[PLACEHOLDER]` de la sección 1 con
   las respuestas, **en prosa** (no YAML, no JSON).
2. Escribí el resultado en
   `~/.claude/plugins/config/mcp-contable/sueldos/CLAUDE.md`. Creá las carpetas intermedias si no
   existen.
3. **No modifiques** la plantilla del plugin ni las secciones 2-8 (grounding, gates, mapa de riesgo):
   esas son fijas. Solo completás la sección 1.
4. Mostrá un resumen del perfil escrito y confirmá con el usuario.

## Grounding

- Este skill no produce liquidaciones ni cifras; si el usuario afirma datos laborales/previsionales,
  aplicá la regla del Paso 2 (sin fuente → `[verify]`).

## Qué este skill NO hace

- **No** escribe el perfil en YAML/JSON: el playbook es **prosa**.
- **No** sobrescribe un perfil existente sin confirmación explícita.
- **No** copia datos de empleados (CUIL, remuneraciones, legajos) al perfil.
- **No** guarda cifras (alícuotas, topes, asignaciones, escalas de CCT, alícuota de ART) en el
  perfil: esas se verifican por connector.
- **No** modifica las secciones de grounding, gates ni el mapa de riesgo del playbook.
