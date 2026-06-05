---
name: perfil-societario
description: >
  Entrevista de configuración del perfil del área societaria y de cumplimiento. Detecta si el perfil ya
  está configurado; si no, entrevista al usuario (rol, entidad/CUIT, tipo societario, régimen,
  jurisdicciones, jurisdicción registral IGJ/RPJEC, terminación de CUIT, regímenes de información,
  carpetas locales) y escribe el perfil personalizado que reemplaza los [PLACEHOLDER] del playbook.
  Usar al instalar el plugin o cuando el usuario pida reconfigurar. Tiene versión quick (~2 min) y full.
user-invocable: true
---

# Cold Start — Entrevista de configuración (societario y cumplimiento)

## Propósito

Personalizar el plugin antes del primer uso real: capturar **rol del usuario**, **entidad/CUIT**,
**tipo societario**, **régimen fiscal**, **jurisdicciones**, **jurisdicción registral (IGJ/RPJEC)**,
**terminación de CUIT**, **regímenes de información aplicables** y **carpetas locales de trabajo**, y
persistir un perfil personalizado tomando como referencia los campos de la plantilla del playbook del
área (`skills/consulta-cumplimiento/playbook.md`, sección 1). El perfil
ajusta el encabezado de work-product, los gates y qué obligaciones de cumplimiento prioriza el área.

## Paso 0 — Detectar si ya está configurado

1. Si existe un **perfil global del estudio**
   (`~/.claude/plugins/config/mcp-contable/perfil-global.md`), leerlo primero: puede tener ya
   el rol, la entidad y las jurisdicciones. Reusar eso y preguntar solo lo que falte.
2. Leé el perfil del área en
   `~/.claude/plugins/config/mcp-contable/perfil-societario.md` si existe; si no, usá como referencia
   de campos la plantilla del playbook del área (`skills/consulta-cumplimiento/playbook.md`).
3. Buscá marcadores `[PLACEHOLDER` en la sección 1 (Perfil).
   - **Sin placeholders** → ya está configurado. Mostrá un resumen y preguntá si quiere **(a)**
     mantenerlo, **(b)** editar un campo, o **(c)** reconfigurar. No sobrescribas sin confirmar.
   - **Con placeholders** → continuá con la entrevista.
4. Preguntá si quiere la versión **quick** (~2 min) o **full**.

## Paso 1 — Entrevista (preguntá de a una, en prosa, conversacional)

**Quick (mínimo imprescindible):**

1. **Rol.** "¿Sos contador/a matriculado/a, o un usuario con/sin acceso a un contador que revise el
   trabajo?" → Mapear a `contador matriculado` | `usuario con acceso a contador` |
   `usuario sin acceso a contador`. (Default conservador si no contesta: sin acceso.)
2. **Entidad y CUIT.** "¿Para qué entidad trabajamos (razón social) y cuál es su CUIT?" Si da un CUIT,
   podés ofrecer verificar la constancia con `arca_get_constancia` (no es obligatorio). El **último
   dígito del CUIT** define el grupo de vencimiento en el calendario ARCA (guardá la **terminación**,
   no la fecha).
3. **Tipo societario.** "¿Qué tipo de sociedad es (SA, SRL, SAS, etc.)?" Define qué obligaciones
   societarias y registrales aplican.
4. **Jurisdicción registral.** "¿Dónde está inscripta la sociedad? En **CABA** el registro es la
   **IGJ**; en **Santa Fe** es el **RPJEC** (Registro Público de Personas Jurídicas, Empresas y
   Contratos, digital). ⚠️ No son lo mismo." → Mapear a la jurisdicción correcta. **No asumir IGJ.**

**Full (además de lo anterior):**

5. **Régimen fiscal.** "¿La entidad es **Responsable Inscripto** o **Monotributo**?" (Default del
   plugin: Responsable Inscripto.)
6. **Jurisdicciones de tributación.** "¿Tributa solo en **Nación (ARCA)** o también en **Santa Fe**?"
7. **Regímenes de información.** "¿La entidad está obligada a presentar regímenes de información (p. ej.
   participaciones societarias, CITI)?" → Guardar **cuáles** (sin afirmar su vigencia ni plazo; eso se
   verifica).
8. **Carpetas locales.** "¿Dónde están las carpetas de trabajo (estatuto, actas, balances presentados,
   comprobantes de presentación) que querés que el sistema pueda consultar?" → Guardar la **ruta** en el
   perfil. **Nunca copiar el contenido al perfil ni al repo** (zero-retention).
9. **Criterios del estudio (opcional).** Preferencias de presentación, criterios propios.

## Paso 2 — Verificar hechos de cumplimiento que afirme el usuario

Si el usuario afirma un dato verificable (p. ej. "el vencimiento de la DDJJ es el día X", "tal régimen
de información sigue vigente", "la presentación del balance vence en tal plazo"), **no lo des por
cierto**: marcalo como **a verificar** y ofrecé recuperarlo con `buscar-normativa-societaria` /
`analizar-norma-societaria` o contra ARCA / el calendario fechado. No incorpores fechas ni vigencias al
perfil sin verificar; el perfil guarda **estructura (tipo societario, jurisdicción registral, regímenes
aplicables), no fechas ni vigencias**.

## Paso 3 — Escribir el perfil

1. Tomá como **referencia de campos** la plantilla del playbook del área
   (`skills/consulta-cumplimiento/playbook.md`, sección 1) y escribí las respuestas **en prosa** (no
   YAML, no JSON).
2. Escribí el resultado en
   `~/.claude/plugins/config/mcp-contable/perfil-societario.md`. Creá las carpetas
   intermedias si no existen.
3. **No modifiques** la plantilla del playbook ni las secciones 2-8 (grounding, gates, mapa de riesgo):
   esas son fijas. Solo completás la sección 1.
4. Mostrá un resumen del perfil escrito y confirmá con el usuario. **Verificá especialmente que la
   jurisdicción registral quedó bien (IGJ solo si es CABA; RPJEC si es Santa Fe).**

## Grounding

- Este skill no produce vencimientos ni presentaciones; si el usuario afirma datos de cumplimiento,
  aplicá la regla del Paso 2 (sin fuente → `[verify]`).

## Qué este skill NO hace

- **No** escribe el perfil en YAML/JSON: el playbook es **prosa**.
- **No** sobrescribe un perfil existente sin confirmación explícita.
- **No** copia datos del contribuyente (datos de socios/accionistas, documentos societarios, montos) al
  perfil.
- **No** guarda fechas de vencimiento ni vigencias de regímenes en el perfil: esas se verifican por
  connector / recurso fechado.
- **No** asume que la jurisdicción registral es la IGJ: la pregunta y la mapea (IGJ = CABA; RPJEC = Santa Fe).
- **No** modifica las secciones de grounding, gates ni el mapa de riesgo del playbook.
