---
name: cold-start-interview
description: >
  Entrevista de configuración inicial del plugin impuestos-liquidaciones. Detecta si el perfil ya
  está configurado; si no, entrevista al usuario (rol, entidad/CUIT, régimen fiscal, jurisdicciones,
  carpetas locales) y escribe el perfil personalizado que reemplaza los [PLACEHOLDER] del playbook.
  Usar al instalar el plugin o cuando el usuario pida reconfigurar. Tiene versión quick (~2 min) y full.
user-invocable: true
---

# Cold Start — Entrevista de configuración (impuestos y liquidaciones)

## Propósito

Personalizar el plugin antes del primer uso real: capturar **rol del usuario**, **entidad/CUIT**,
**régimen fiscal**, **jurisdicciones**, **impuestos activos** y **carpetas locales de trabajo**, y
persistir un perfil personalizado tomando como referencia los campos de la plantilla del playbook del
área (`skills/consulta-impuestos/playbook.md`, sección 1). El
perfil ajusta el encabezado de work-product, los gates y qué impuestos prioriza el área.

## Paso 0 — Detectar si ya está configurado

1. Si existe un **perfil global del estudio**
   (`~/.claude/plugins/config/mcp-contable/perfil-global.md`), leerlo primero: puede
   tener ya el rol, la entidad y las jurisdicciones. Reusar eso y preguntar solo lo que falte.
2. Leé el perfil del área en
   `~/.claude/plugins/config/mcp-contable/perfil-impuestos.md` si existe; si no, usá como
   referencia de campos la plantilla del playbook del área (`skills/consulta-impuestos/playbook.md`).
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
2. **Entidad y CUIT.** "¿Para qué entidad trabajamos (razón social) y cuál es su CUIT?" Si da un
   CUIT, podés ofrecer verificar la constancia con `arca_get_constancia` (no es obligatorio).
3. **Régimen fiscal.** "¿La entidad es **Responsable Inscripto** (IVA + Ganancias) o **Monotributo**?"
   (Default del plugin: Responsable Inscripto.)
4. **Jurisdicciones.** "¿Tributa solo en **Nación (ARCA)**, o también **Ingresos Brutos en Santa
   Fe**? ¿En más de una provincia (Convenio Multilateral)?"

**Full (además de lo anterior):**

5. **Impuestos activos.** "¿Qué impuestos liquida habitualmente? (IVA, Ganancias, IIBB Santa Fe,
   Bienes Personales, retenciones/percepciones)."
6. **Carpetas locales.** "¿Dónde están las carpetas de trabajo (facturas, papeles de trabajo, DDJJ)
   que querés que el sistema pueda consultar?" → Guardar la **ruta** en el perfil. **Nunca copiar el
   contenido al perfil ni al repo** (zero-retention).
7. **Criterios del estudio (opcional).** Preferencias de presentación, criterios propios.

## Paso 2 — Verificar hechos fiscales que afirme el usuario

Si el usuario afirma un dato fiscal verificable (p. ej. "la alícuota de IVA bajó", "el tope de
monotributo categoría X es $...", "tal RG está derogada"), **no lo des por cierto**: marcalo como
**a verificar** y ofrecé recuperarlo con `buscar-normativa-fiscal` / `analizar-norma-fiscal` o
contra ARCA. No incorpores cifras al perfil sin verificar; el perfil guarda **régimen y estructura,
no montos**.

## Paso 3 — Escribir el perfil

1. Tomá como **referencia de campos** la plantilla del playbook del área
   (`skills/consulta-impuestos/playbook.md`, sección 1) y escribí las respuestas **en prosa** (no
   YAML, no JSON).
2. Escribí el resultado en
   `~/.claude/plugins/config/mcp-contable/perfil-impuestos.md`. Creá las carpetas
   intermedias si no existen.
3. **No modifiques** la plantilla del playbook ni las secciones 2-8 (grounding, gates, mapa de riesgo):
   esas son fijas. Solo completás la sección 1.
4. Mostrá un resumen del perfil escrito y confirmá con el usuario.

## Grounding

- Este skill no produce liquidaciones ni cifras; si el usuario afirma datos fiscales, aplicá la
  regla del Paso 2 (sin fuente → `[verify]`).

## Qué este skill NO hace

- **No** escribe el perfil en YAML/JSON: el playbook es **prosa**.
- **No** sobrescribe un perfil existente sin confirmación explícita.
- **No** copia datos del contribuyente (montos, documentos, CUITs de terceros) al perfil.
- **No** guarda cifras fiscales (alícuotas, topes) en el perfil: esas se verifican por connector.
- **No** modifica las secciones de grounding, gates ni el mapa de riesgo del playbook.
