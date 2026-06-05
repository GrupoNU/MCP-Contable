---
name: perfil-registracion
description: >
  Entrevista de configuración del perfil del área de registración y estados contables. Detecta si el perfil
  ya está configurado; si no, entrevista al usuario (rol, ente/CUIT, tamaño del ente, normas contables
  aplicables, cierre de ejercicio, libros, carpetas locales) y escribe el perfil personalizado que
  reemplaza los [PLACEHOLDER] del playbook. Usar al instalar el plugin o cuando el usuario pida
  reconfigurar. Tiene versión quick (~2 min) y full.
user-invocable: true
---

# Cold Start — Entrevista de configuración (registración y estados contables)

## Propósito

Personalizar el plugin antes del primer uso real: capturar **rol del usuario**, **ente/CUIT**,
**tamaño del ente**, **normas contables aplicables**, **cierre de ejercicio**, **libros contables** y
**carpetas locales de trabajo**, y persistir un perfil personalizado tomando como referencia los
campos de la plantilla del playbook del área (`skills/consulta-registracion/playbook.md`, sección 1).
El perfil ajusta el encabezado de work-product, los gates y qué normas
prioriza el área.

## Paso 0 — Detectar si ya está configurado

1. Si existe un **perfil global del estudio**
   (`~/.claude/plugins/config/mcp-contable/perfil-global.md`), leerlo primero: puede tener
   ya el rol, el ente y las normas aplicables. Reusar eso y preguntar solo lo que falte.
2. Leé el perfil del área en
   `~/.claude/plugins/config/mcp-contable/perfil-registracion.md` si existe; si no,
   usá como referencia de campos la plantilla del playbook del área (`skills/consulta-registracion/playbook.md`).
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
2. **Ente y CUIT.** "¿Para qué entidad trabajamos (razón social) y cuál es su CUIT?" Si da un CUIT,
   podés ofrecer verificar la constancia con `arca_get_constancia` (no es obligatorio).
3. **Tipo y tamaño del ente.** "¿Es una **sociedad** (LGS 19.550) o **unipersonal**? ¿Sabés si
   califica como **ente pequeño/mediano** (RT 41/42)?" → El encuadre de tamaño se **confirma contra
   FACPCE**; no fijar un umbral de memoria.
4. **Cierre de ejercicio.** "¿Cuál es la fecha de cierre del ejercicio económico? (ej. 31/12)."

**Full (además de lo anterior):**

5. **Normas contables aplicables.** "¿El ente aplica las **RT de la FACPCE** tal como las adopta el
   **CPCE de su jurisdicción**? ¿Aplica reexpresión por inflación (RT 6)?" → La **vigencia/activación**
   del ajuste y la adopción provincial se **verifican**; no asumir.
6. **Libros contables.** "¿Qué libros lleva (Diario, Inventarios y Balances, subdiarios)? ¿Soporte
   papel rubricado o digital? ¿Estado de rúbrica?"
7. **Carpetas locales.** "¿Dónde están las carpetas de trabajo (comprobantes, papeles de trabajo,
   mayores) que querés que el sistema pueda consultar?" → Guardar la **ruta** en el perfil. **Nunca
   copiar el contenido al perfil ni al repo** (zero-retention).
8. **Criterios del estudio (opcional).** Plan de cuentas propio, criterios de exposición.

## Paso 2 — Verificar hechos contables/normativos que afirme el usuario

Si el usuario afirma un dato verificable (p. ej. "la RT 17 dice X", "el coeficiente de ajuste del mes
es Y", "tal RT está derogada", "el umbral de ente pequeño es Z"), **no lo des por cierto**: marcalo
como **a verificar** y ofrecé recuperarlo con `buscar-normativa-contable` / `analizar-norma-contable`
o verificarlo manualmente contra `facpce.org.ar`. No incorpores citas de RT ni coeficientes al
perfil sin verificar; el perfil guarda **estructura del ente y normas aplicables, no coeficientes ni
transcripciones de RT**.

## Paso 3 — Escribir el perfil

1. Tomá como **referencia de campos** la plantilla del playbook del área
   (`skills/consulta-registracion/playbook.md`, sección 1) y escribí las respuestas **en prosa** (no
   YAML, no JSON).
2. Escribí el resultado en
   `~/.claude/plugins/config/mcp-contable/perfil-registracion.md`. Creá las
   carpetas intermedias si no existen.
3. **No modifiques** la plantilla del playbook ni las secciones 2-8 (grounding, gates, mapa normativo):
   esas son fijas. Solo completás la sección 1.
4. Mostrá un resumen del perfil escrito y confirmá con el usuario.

## Grounding

- Este skill no produce asientos ni estados contables; si el usuario afirma datos normativos
  (número/objeto/vigencia de una RT) o coeficientes, aplicá la regla del Paso 2 (sin fuente →
  `[verify]`; las RT se verifican manualmente contra FACPCE).

## Qué este skill NO hace

- **No** escribe el perfil en YAML/JSON: el playbook es **prosa**.
- **No** sobrescribe un perfil existente sin confirmación explícita.
- **No** copia datos del ente (saldos, comprobantes, CUITs de terceros) al perfil.
- **No** guarda citas de RT ni coeficientes de ajuste en el perfil: esos se verifican contra FACPCE.
- **No** fija un umbral de "ente pequeño/mediano" de memoria: se confirma contra FACPCE.
- **No** modifica las secciones de grounding, gates ni el mapa normativo del playbook.
