---
name: consulta-registracion
description: >
  Punto de entrada para una consulta de registración o estados contables (asientos y partida doble,
  libros contables, balance, estados contables, ajuste por inflación, RT de la FACPCE). Aplica el
  playbook del plugin + reglas de grounding, distingue el marco conceptual estable de la cita
  normativa que se verifica, y deriva a buscar-normativa-contable / analizar-norma-contable cuando
  hace falta fuente. Nunca afirma número/objeto/vigencia de una RT ni coeficientes sin verificar.
  Usar para preguntas contables generales de registración y estados contables.
user-invocable: true
---

# Consulta de registración y estados contables

## Propósito

Responder una consulta de registración o estados contables aplicando el **playbook** del área
(`playbook.md`, en esta misma carpeta de skill) y las
reglas de **grounding**, **distinguiendo el marco conceptual estable** (partida doble, asientos,
rubros) **de la cita normativa concreta** (qué RT regula un tratamiento, su número, objeto y
vigencia), derivando a los skills de fuente cuando la respuesta requiere una norma o una verificación.
Salida = **borrador** para revisión de un contador matriculado.

## Procedimiento

1. **Verificar perfil:** si el playbook tiene `[PLACEHOLDER]` en la sección 1, ofrecé correr
   `/mcp-contable:perfil-registracion` antes de producir trabajo sustantivo. Si no,
   usá el rol/ente/normas del perfil.
2. **Encabezado de work-product** según el rol (playbook §2). Si el rol es `[PLACEHOLDER]`, usá el
   encabezado de no-contador (conservador).
3. **Clasificar la consulta y separar marco de cita** (playbook §3-§5):
   - **Marco conceptual estable → se explica** sin cita de RT: partida doble (debe = haber),
     naturaleza de las cuentas, estructura de un asiento, mayorización, qué son los estados contables
     básicos (Situación Patrimonial, Resultados, Evolución del PN, Flujo de Efectivo).
   - **Cita normativa concreta → se verifica**: "esto lo regula la RT N°X", "la RT X dice
     exactamente Y", el **objeto/número/vigencia** de una RT (16, 17, 6, 8, 9, 41/42), el encuadre
     de ente pequeño/mediano, los criterios de medición/exposición específicos.
   - **Coeficiente de ajuste por inflación / índice (RT 6) → MUY ALTO**: verificar siempre; nunca de
     memoria.
4. **Decidir grounding:**
   - Si la respuesta necesita el **número/objeto/vigencia de una RT, un coeficiente o un criterio
     normado** → **no lo afirmes de memoria.** Para el marco legal (CCyC/LGS) derivá a
     `buscar-normativa-contable` / `analizar-norma-contable`. Para una **RT de la FACPCE (sin
     connector)**, indicá que la cita se **verifica manualmente contra `facpce.org.ar`** y marcala
     `[verify]`. Sin fuente → marco conceptual + `[verify]`.
   - Para el **marco conceptual** (cómo se registra un asiento, qué es un rubro, qué estados existen),
     podés explicar en general, recordando que la **cita de la RT que lo respalda se verifica**.
5. **Distinguir vigente de proyecto:** si la consulta toca una RT en consulta/borrador o una reforma
   de norma "que se viene", **no la trates como vigente** sin confirmar aprobación de la FACPCE y
   adopción provincial.
6. **Aplicar gates** (playbook §6):
   - **Gate de consecuencias:** si la consulta deriva en **registrar un asiento que cierra un
     período**, **emitir estados contables para presentación**, **cerrar el ejercicio** o generar un
     asiento de ajuste por inflación que impacta resultados → pedí **confirmación** y recordá que un
     contador matriculado revisa, verifica el encuadre y las cifras y asume la responsabilidad. No
     avances a "registrar/emitir/cerrar" sin confirmación.
7. **Cerrar** recordando que la respuesta es un **borrador para revisión de un contador matriculado**.

## Grounding

- Sin tool result de Tier A/B en contexto, **toda cita normativa/coeficiente lleva `[verify]`**.
- Mostrá `source_url` + `retrieved_at` + tier en lo que provenga de connectors.
- **Las RT de la FACPCE no tienen connector**: su número/objeto/vigencia se verifican **manualmente
  contra `facpce.org.ar`** → marcá `[verify]` hasta confirmar.
- Ajuste por inflación (RT 6): el **coeficiente/índice** se verifica siempre; si no podés, declaralo
  con `[verify]` fuerte y **no afirmes el número ni la vigencia del ajuste**.

## Qué este skill NO hace

- **No** afirma número, objeto ni vigencia de una RT de memoria como verdad fija: la cita se verifica
  contra FACPCE (o marca `[verify]`).
- **No** da un coeficiente de ajuste por inflación ni un índice de memoria.
- **No** confunde el marco conceptual (estable, se explica) con la cita normativa (se verifica).
- **No** presenta un proyecto/borrador de RT como norma vigente sin verificar aprobación/adopción.
- **No** registra asientos de cierre, emite estados ni cierra el ejercicio sin confirmación del usuario.
- **No** es asesoramiento contable: la respuesta es un borrador para el contador matriculado.
