---
name: consulta-cumplimiento
description: >
  Punto de entrada para una consulta de cumplimiento societario y registral (vencimientos ARCA,
  regímenes de información, obligaciones de la Ley General de Sociedades 19.550, presentación de
  estados contables, trámites registrales IGJ/RPJEC). Aplica el playbook del plugin + reglas de
  grounding, identifica el tema y su riesgo de alucinación, y deriva a buscar-normativa-societaria /
  analizar-norma-societaria cuando hace falta fuente. Nunca afirma fechas de vencimiento ni vigencia
  de regímenes sin verificar. Usar para preguntas de cumplimiento generales.
user-invocable: true
---

# Consulta de cumplimiento

## Propósito

Responder una consulta de cumplimiento societario y registral aplicando el **playbook** del área
(`playbook.md`, en esta misma carpeta de skill) y
las reglas de **grounding**, derivando a los skills de fuente cuando la respuesta requiere una norma,
una RG, un calendario fechado o un trámite verificado. Salida = **borrador** para revisión de un
contador matriculado.

## Procedimiento

1. **Verificar perfil:** si el playbook tiene `[PLACEHOLDER]` en la sección 1, ofrecé correr
   `/mcp-contable:perfil-societario-contable` antes de producir trabajo sustantivo. Si no, usá el
   rol/tipo societario/jurisdicción registral/régimen/jurisdicciones del perfil.
2. **Encabezado de work-product** según el rol (playbook §2). Si el rol es `[PLACEHOLDER]`, usá el
   encabezado de no-contador (conservador).
3. **Clasificar la consulta y su riesgo** (playbook §4):
   - **Vencimientos ARCA** (impositivos / seguridad social por terminación de CUIT) → **MUY ALTO**
     (la fecha cambia cada año por RG; verificar siempre).
   - **Regímenes de información** (participaciones societarias, CITI, otros) → **MUY ALTO** (vigencia y
     plazo por RG; verificar).
   - **LGS 19.550** (tipos societarios, obligaciones de administradores, órganos) → marco conceptual
     citable vía InfoLEG; distinguir vigente de proyecto de reforma.
   - **Presentación de estados contables / trámites registrales** → **ALTO**; plazo y requisitos
     **dependen de la jurisdicción registral** (IGJ en CABA / RPJEC en Santa Fe). No extrapolar.
4. **Decidir grounding:**
   - Si la respuesta necesita una **fecha de vencimiento, un plazo de presentación, la vigencia de un
     régimen o un requisito registral concreto** → **derivá a `buscar-normativa-societaria`** (y si hace
     falta el texto, a `analizar-norma-societaria`). **No afirmes la fecha ni la vigencia de memoria.**
     Sin fuente → marco conceptual + `[verify]`.
   - Para el **marco conceptual** (qué es un régimen de información, qué obligación societaria existe,
     cómo se estructura el calendario por terminación de CUIT), podés explicar en general, recordando que
     la **fecha/plazo/vigencia concretos se verifican**.
5. **Jurisdicción registral:** antes de describir cualquier trámite registral, **confirmá la jurisdicción
   del perfil**. **IGJ = solo CABA; RPJEC = Santa Fe** (100% digital desde 2025, no es la IGJ). **No
   extrapoles** un trámite de una jurisdicción a la otra. El RPJEC **requiere login → flujo asistido**:
   describí el procedimiento general y marcá que se confirma manualmente contra el RPJEC (`[verify]`).
   Normativa registral provincial: `santafe_sin`.
6. **Aplicar gates** (playbook §6):
   - **Gate de consecuencias:** si la consulta deriva en preparar/presentar un **régimen de información**,
     una **DDJJ societaria**, una **inscripción registral** o la **presentación de estados contables** →
     pedí **confirmación** y recordá que un contador matriculado revisa, verifica los plazos/requisitos
     vigentes y asume la responsabilidad. No avances a "presentar/inscribir" sin confirmación.
7. **Cerrar** recordando que la respuesta es un **borrador para revisión de un contador matriculado**.

## Grounding

- Sin tool result de Tier A/B en contexto (o recurso estático fechado), **toda fecha/cita/régimen lleva
  `[verify]`**.
- Mostrá `source_url` + `retrieved_at` + tier en lo que provenga de connectors.
- Vencimientos ARCA, regímenes de información y reformas: verificá siempre; si no podés, declaralo con
  `[verify]` fuerte y **no afirmes la fecha, el plazo ni la vigencia**.
- El calendario de ARCA es **recurso estático con fecha de corte**: si pasó tiempo, `[verify]` y
  reconfirmar la RG del año.

## Qué este skill NO hace

- **No** afirma una fecha de vencimiento de ARCA ni provincial sin derivar a fuente (o marcando `[verify]`).
- **No** afirma que un régimen de información está vigente ni su plazo sin recuperar la RG vigente.
- **No** extrapola trámites de IGJ (CABA) a Santa Fe (RPJEC), ni viceversa.
- **No** presenta una reforma/proyecto (de la LGS o un nuevo régimen) como vigente sin verificar la entrada en vigor.
- **No** ejecuta acciones con consecuencias (presentar régimen/DDJJ, inscribir) sin confirmación del usuario.
- **No** es asesoramiento contable, impositivo ni legal: la respuesta es un borrador para el contador matriculado.
