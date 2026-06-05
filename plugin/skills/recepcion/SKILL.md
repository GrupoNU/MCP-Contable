---
name: recepcion
description: >
  Puerta única del estudio contable. Recibe una consulta contable/impositiva en lenguaje natural, la
  clasifica por área (impuestos, sueldos, registración, societario) y deriva al skill de entrada del
  área correcta. Si la consulta cruza varias áreas, la descompone en pasos ordenados y deriva a cada
  una. No produce contenido fiscal sustantivo: delega. Usar como entrada general al estudio.
user-invocable: true
---

# Recepción del estudio contable

## Propósito

Ser el **punto de entrada único** del estudio: clasificar una consulta y **derivarla** al área
especialista correcta, sin resolverla uno mismo. Para consultas que cruzan áreas, descomponerlas y
ordenar los pasos. Salida = un **plan de derivación**, no la respuesta de fondo.

## Procedimiento

1. **Verificar perfil global:** si el playbook tiene `[PLACEHOLDER]` en la sección 1, ofrecé correr
   `/mcp-contable:cold-start-interview` antes de derivar trabajo sustantivo (así el área no
   re-pregunta el rol/régimen/jurisdicciones).
2. **Encabezado de work-product** según el rol (playbook §2). Si es `[PLACEHOLDER]`, usá el de
   no-contador (conservador).
3. **Clasificar la consulta** con el mapa de áreas (playbook §3) y sus señales:
   - impuestos (IVA/Ganancias/IIBB/monotributo/retenciones) → `impuestos-liquidaciones`.
   - nómina/cargas sociales/F.931/ART → `sueldos`.
   - asientos/libros/balance/estados contables/RT → `registracion-estados-contables`.
   - vencimientos/regímenes de información/IGJ/RPJEC/inscripciones → `societario-cumplimiento`.
4. **Derivar:**
   - **Una sola área:** derivá al skill de entrada del área (p. ej.
     `/mcp-contable:consulta-impuestos`), pasando el contexto del perfil global.
   - **Varias áreas (transversal):** descomponé la consulta en pasos por área, en orden lógico,
     explicá el plan al usuario y derivá a cada skill de entrada.
   - **Ambigüedad:** hacé 1 pregunta para desambiguar antes de derivar. No adivines el área.
5. **No resolver de fondo:** no des la alícuota, el asiento, la liquidación ni el vencimiento — eso
   lo hace el área con su propio grounding. Tu entregable es la derivación (a qué área, en qué orden).
6. **Recordar gates** (playbook §5): si la consulta apunta a una acción con consecuencias (presentar
   DDJJ, generar F.931, registrar cierre, recategorizar, inscribir), avisá que requiere confirmación
   y revisión profesional, y dejá que el área aplique el gate.

## Ejemplos de clasificación

- "¿Cuánto me da el IVA de este mes?" → **impuestos-liquidaciones** (una sola área).
- "Liquidame el sueldo de un empleado del convenio X" → **sueldos**.
- "¿Cómo registro la compra de un rodado?" → **registracion-estados-contables**.
- "¿Cuándo vence mi DDJJ de Ganancias?" → **societario-cumplimiento** (vencimientos) y/o
  **impuestos-liquidaciones** (según si pide la fecha o el cálculo).
- "Ayudame a cerrar el mes" → **transversal**: IVA (impuestos) + F.931 (sueldos) + vencimientos
  (societario) → descomponer y derivar en orden.

## Grounding

- Este skill **no cita normas ni cifras** (es recepción). Al derivar, recordá que el área aplicará
  grounding estricto (sin fuente → `[verify]`).
- Toda salida del estudio es un **borrador para revisión de un contador matriculado**.

## Qué este skill NO hace

- **No** resuelve la consulta de fondo (no da alícuotas, asientos, liquidaciones ni vencimientos).
- **No** cita normativa: deriva al área que sí lo hace con grounding.
- **No** adivina el área cuando hay ambigüedad: pregunta para desambiguar.
- **No** ejecuta acciones con consecuencias: recuerda el gate y deriva al área.
- **No** es asesoramiento contable: la derivación es el primer paso de un trabajo que revisa un
  contador matriculado.
