---
name: cold-start-interview
description: >
  Entrevista de configuración del perfil GLOBAL del estudio contable (rol, entidad/CUIT, régimen,
  jurisdicciones, carpetas locales). Lo escribe una sola vez y las áreas lo leen antes que su propio
  perfil, evitando reconfigurar lo mismo en cada plugin. Usar al instalar el estudio o para
  reconfigurar el perfil común.
user-invocable: true
---

# Cold Start — Perfil global del estudio

## Propósito

Capturar **una sola vez** el perfil común del estudio (rol, entidad/CUIT, régimen fiscal,
jurisdicciones, carpetas locales) y persistirlo donde las áreas lo lean antes que su propio perfil.
Evita que el usuario reconfigure lo mismo en cada plugin (impuestos, sueldos, etc.).

## Paso 0 — Detectar si ya está configurado

1. Leé el perfil global en `~/.claude/plugins/config/mcp-contable/perfil-global.md` si
   existe; si no, usá como referencia de campos la plantilla del playbook de un área (p. ej.
   `skills/consulta-impuestos/playbook.md`).
2. Buscá `[PLACEHOLDER` en la sección 1.
   - **Sin placeholders** → ya está configurado. Mostrá un resumen y preguntá si quiere mantenerlo,
     editar un campo, o reconfigurar. No sobrescribas sin confirmar.
   - **Con placeholders** → continuá con la entrevista.

## Paso 1 — Entrevista (preguntá de a una, conversacional)

1. **Rol.** "¿Sos contador/a matriculado/a, o un usuario con/sin acceso a un contador que revise el
   trabajo?" → `contador matriculado` | `usuario con acceso a contador` | `usuario sin acceso a contador`.
   (Default conservador: sin acceso.)
2. **Entidad y CUIT.** "¿Para qué entidad trabajamos (razón social) y su CUIT?" (Podés ofrecer
   verificar la constancia con el área de impuestos; no es obligatorio acá.)
3. **Régimen fiscal.** "¿Responsable Inscripto o Monotributo?" (Default: Responsable Inscripto.)
4. **Jurisdicciones.** "¿Nación (ARCA), Santa Fe (IIBB), ambas? ¿Convenio Multilateral?"
5. **Carpetas locales.** "¿Dónde están las carpetas de trabajo (facturas, papeles de trabajo, DDJJ,
   recibos)?" → Guardar la **ruta** en el perfil. **Nunca copiar el contenido** (zero-retention).
6. **Áreas activas.** "¿Qué áreas vas a usar? (impuestos, sueldos, registración, societario)."

## Paso 2 — No incorporar afirmaciones fiscales sin verificar

Si el usuario afirma un dato fiscal/contable verificable (una alícuota, un tope, una vigencia), no
lo guardes como cierto: el perfil guarda **rol, entidad, régimen, jurisdicciones y rutas**, NO
cifras. Las cifras se verifican en las áreas por connector.

## Paso 3 — Escribir el perfil global

1. Tomá como **referencia de campos** la plantilla del playbook de un área (`skills/consulta-<area>/playbook.md`,
   sección 1) y escribí las respuestas **en prosa**.
2. Escribí el resultado en `~/.claude/plugins/config/mcp-contable/perfil-global.md`. Creá
   las carpetas intermedias si no existen.
3. **No modifiques** las demás secciones de los playbooks (mapa de áreas, reglas de derivación).
4. Mostrá un resumen y confirmá. Avisá que las áreas leerán este perfil y solo preguntarán lo
   específico de cada una.

## Grounding

- Este skill no produce cifras; si el usuario afirma datos fiscales, no los guarda como ciertos (se
  verifican en las áreas).

## Qué este skill NO hace

- **No** escribe el perfil en YAML/JSON: es **prosa**.
- **No** sobrescribe un perfil existente sin confirmación.
- **No** copia datos del contribuyente (montos, documentos) al perfil; solo la ruta de las carpetas.
- **No** guarda cifras fiscales en el perfil.
- **No** reemplaza el cold-start de cada área: captura lo común; cada área pregunta lo suyo.
