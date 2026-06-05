---
name: consulta-sueldos
description: >
  Punto de entrada para una consulta de nómina general (liquidación de haberes, conceptos
  remunerativos/no remunerativos, cargas sociales, F.931, ART, convenios colectivos, SAC, vacaciones,
  indemnizaciones). Aplica el playbook del plugin + reglas de grounding, identifica el tema y su
  riesgo de alucinación, y deriva a buscar-normativa-laboral / analizar-norma-laboral cuando hace
  falta fuente. Nunca afirma alícuotas/topes/asignaciones/escalas sin verificar. Usar para preguntas
  de sueldos generales.
user-invocable: true
---

# Consulta de sueldos

## Propósito

Responder una consulta de nómina general aplicando el **playbook** del área (`playbook.md`, en esta
misma carpeta de skill) y las reglas de
**grounding**, derivando a los skills de fuente cuando la respuesta requiere una norma o una cifra
verificada. Salida = **borrador** para revisión de un contador matriculado.

## Procedimiento

1. **Verificar perfil:** si el playbook tiene `[PLACEHOLDER]` en la sección 1, ofrecé correr
   `/mcp-contable:perfil-sueldos` antes de producir trabajo sustantivo. Si no, usá el
   rol/régimen/jurisdicciones/convenio/ART del perfil.
2. **Encabezado de work-product** según el rol (playbook §2). Si el rol es `[PLACEHOLDER]`, usá el
   encabezado de no-contador (conservador).
3. **Clasificar la consulta y su riesgo** (playbook §4):
   - LCT / conceptos remunerativos vs. no remunerativos → marco conceptual citable, pero
     **calificación concreta y montos = ALTO** (verificar).
   - Cargas sociales (alícuotas de aportes/contribuciones, composición por subsistema) → **MUY ALTO** (verificar siempre).
   - Tope/mínimo de la base imponible de seguridad social → **MUY ALTO** (cambia por movilidad; verificar).
   - Asignaciones familiares (montos, rangos de IGF) → **MUY ALTO** (movilidad; verificar).
   - Escalas de convenio (CCT) → **MUY ALTO** (paritarias; verificar el acuerdo vigente).
   - F.931 → **ALTO**: explicar qué es y cómo se compone; no inventar montos ni el cálculo.
   - ART → **ALTO**: la alícuota la fija la aseguradora; no afirmarla.
   - Reforma laboral 2024-2026 (Ley 27.742) → **ALTO**; distinguir vigente de proyecto; no confundir
     con la reforma fiscal (Ley 27.743).
4. **Decidir grounding:**
   - Si la respuesta necesita una **alícuota, tope, mínimo, monto de asignación, escala de convenio,
     alícuota de ART o tope indemnizatorio** → **derivá a `buscar-normativa-laboral`** (y si hace
     falta el texto, a `analizar-norma-laboral`). **No afirmes el número de memoria.** Sin fuente →
     marco conceptual + `[verify]`.
   - Para el **marco conceptual** (cómo se liquida un haber, qué integra la remuneración, cómo se
     calcula el SAC o las vacaciones, qué es el F.931), podés explicar en general, recordando que el
     valor concreto se verifica.
5. **Convenio y jurisdicción:** si la consulta depende del CCT, confirmá el convenio aplicable (del
   perfil) y recordá que la escala se verifica. Para normativa provincial usá `santafe_sin` /
   `santafe_fiscal`.
6. **Aplicar gates** (playbook §6):
   - **Gate de consecuencias:** si la consulta deriva en liquidar sueldos para pago, emitir un
     recibo, preparar/presentar un F.931, registrar el asiento de sueldos o calcular una
     indemnización/saldo a depositar → pedí **confirmación** y recordá que un contador matriculado
     revisa, verifica las cifras y asume la responsabilidad. No avances a "liquidar/presentar/generar"
     sin confirmación.
7. **Cerrar** recordando que la respuesta es un **borrador para revisión de un contador matriculado**.

## Grounding

- Sin tool result de Tier A/B en contexto, **toda cifra/cita lleva `[verify]`**.
- Mostrá `source_url` + `retrieved_at` + tier en lo que provenga de connectors.
- Cargas sociales, topes de base imponible, asignaciones familiares y escalas de convenio: verificá
  siempre; si no podés, declaralo con `[verify]` fuerte y **no afirmes el número ni la vigencia**.

## Qué este skill NO hace

- **No** afirma alícuotas, topes de base imponible, mínimos, asignaciones familiares, escalas de CCT
  ni alícuotas de ART sin derivar a fuente (o marcando `[verify]`).
- **No** transcribe una escala salarial de convenio ni una tabla de asignaciones de memoria.
- **No** inventa el cálculo ni los montos del F.931.
- **No** presenta una reforma/proyecto laboral como vigente sin verificar la entrada en vigor.
- **No** ejecuta acciones con consecuencias (liquidar/presentar/emitir/registrar) sin confirmación del usuario.
- **No** es asesoramiento contable, laboral ni previsional: la respuesta es un borrador para el contador matriculado.
