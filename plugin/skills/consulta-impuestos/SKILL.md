---
name: consulta-impuestos
description: >
  Punto de entrada para una consulta impositiva general (IVA, Ganancias, IIBB Santa Fe, monotributo,
  Bienes Personales, retenciones/percepciones). Aplica el playbook del plugin + reglas de grounding,
  identifica el tema y su riesgo de alucinación, y deriva a buscar-normativa-fiscal /
  analizar-norma-fiscal cuando hace falta fuente. Nunca afirma alícuotas/topes/montos sin verificar.
  Usar para preguntas impositivas generales.
user-invocable: true
---

# Consulta de impuestos

## Propósito

Responder una consulta impositiva general aplicando el **playbook** del área (`playbook.md`, en esta
misma carpeta de skill) y las reglas de
**grounding**, derivando a los skills de fuente cuando la respuesta requiere una norma o una cifra
verificada. Salida = **borrador** para revisión de un contador matriculado.

## Procedimiento

1. **Verificar perfil:** si el playbook tiene `[PLACEHOLDER]` en la sección 1, ofrecé correr
   `/mcp-contable:perfil-impuestos` antes de producir trabajo sustantivo. Si no, usá
   el rol/régimen/jurisdicciones del perfil.
2. **Encabezado de work-product** según el rol (playbook §2). Si el rol es `[PLACEHOLDER]`, usá el
   encabezado de no-contador (conservador).
3. **Clasificar la consulta y su riesgo** (playbook §4):
   - IVA / Ganancias / IIBB → marco conceptual citable, pero **alícuotas/montos = ALTO** (verificar).
   - Monotributo (categorías/topes/cuotas) → **MUY ALTO** (verificar siempre; recurso fechado + `[verify]`).
   - Retenciones/percepciones → **MUY ALTO** (alícuotas por RG ARCA; verificar).
   - Bienes Personales / reformas 2024-2026 (Ley 27.743, REIBP, blanqueo) → **ALTO**; distinguir
     vigente de proyecto.
4. **Decidir grounding:**
   - Si la respuesta necesita una **alícuota, tope, mínimo, categoría, valor de unidad o
     vencimiento** → **derivá a `buscar-normativa-fiscal`** (y si hace falta el texto, a
     `analizar-norma-fiscal`). **No afirmes el número de memoria.** Sin fuente → marco conceptual + `[verify]`.
   - Para el **marco conceptual** (cómo se liquida un impuesto, qué es débito/crédito fiscal, base
     imponible), podés explicar en general, recordando que el porcentaje concreto se verifica.
5. **Jurisdicción:** si la consulta es de Ingresos Brutos, confirmá la jurisdicción (Santa Fe) y si
   hay **Convenio Multilateral** (no asumir que todo tributa en SF). Para IIBB SF usá `santafe_sin` /
   `santafe_fiscal`.
6. **Aplicar gates** (playbook §6):
   - **Gate de consecuencias:** si la consulta deriva en preparar/presentar una DDJJ, generar un
     F.931, recategorizar en monotributo o calcular un saldo a depositar → pedí **confirmación** y
     recordá que un contador matriculado revisa, verifica las cifras y asume la responsabilidad. No
     avances a "presentar/generar" sin confirmación.
7. **Cerrar** recordando que la respuesta es un **borrador para revisión de un contador matriculado**.

## Grounding

- Sin tool result de Tier A/B en contexto, **toda cifra/cita lleva `[verify]`**.
- Mostrá `source_url` + `retrieved_at` + tier en lo que provenga de connectors.
- Monotributo, retenciones/percepciones y reformas 2024-2026: verificá siempre; si no podés,
  declaralo con `[verify]` fuerte y **no afirmes el número ni la vigencia**.

## Qué este skill NO hace

- **No** afirma alícuotas, topes, mínimos, categorías ni vencimientos sin derivar a fuente (o
  marcando `[verify]`).
- **No** transcribe una tabla de monotributo de memoria.
- **No** presenta una reforma/proyecto como vigente sin verificar la entrada en vigor.
- **No** ejecuta acciones con consecuencias fiscales (presentar/generar) sin confirmación del usuario.
- **No** es asesoramiento contable ni impositivo: la respuesta es un borrador para el contador matriculado.
