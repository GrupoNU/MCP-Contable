# Recurso estático — Categorías de Monotributo

> ⚠️ **RECURSO ESTÁTICO CON FECHA DE CORTE — Tier A solo a la fecha de captura.**
> **Fecha de corte:** `[SIN COMPLETAR — este recurso es una PLANTILLA]`
> **Fuente oficial:** ARCA (ex-AFIP) — monotributo. https://www.arca.gob.ar
>
> 🚨 **Los topes, cuotas y valores del monotributo se actualizan por IPC (habitualmente
> semestral).** Cualquier valor que se cargue acá queda desactualizado al poco tiempo. Por eso:
> - **Mientras la "Fecha de corte" diga "SIN COMPLETAR", este archivo NO contiene valores válidos.**
> - Aun con fecha de corte completa, si pasó el semestre, tratar TODO valor como **`[verify]`** y
>   reconfirmar contra ARCA antes de usarlo en una liquidación o recategorización.
> - **Este recurso NO reemplaza la verificación contra ARCA.** Es un punto de partida fechado, no
>   una fuente viva.

---

## Cómo se usa este recurso

1. Para **completarlo**: alguien recupera la tabla vigente desde ARCA (o desde la RG de ARCA que la
   fija), la transcribe acá, y **anota la fecha de corte y el número de RG** en la cabecera.
2. Para **usarlo**: leerlo solo si la fecha de corte es reciente (mismo semestre). Si no, marcar
   `[verify]` y reconfirmar contra ARCA. Mostrar siempre fecha de corte + fuente al citar.
3. **Nunca** completar esta tabla "de memoria" de un LLM: los valores deben venir de ARCA con su
   fecha. Si no hay fuente, dejar los campos en `[verify]` — **no inventar**.

---

## Tabla de categorías (PLANTILLA — completar desde ARCA con fecha)

> Estructura de referencia. Las columnas de **valores** se completan SOLO con datos recuperados de
> ARCA a una fecha. Mientras estén en `[verify]`, no usar para liquidar.

| Categoría | Tope de ingresos brutos anuales | Actividad (límites) | Cuota mensual (impuesto integrado + SIPA + OS) |
|---|---|---|---|
| A | `[verify]` | `[verify]` | `[verify]` |
| B | `[verify]` | `[verify]` | `[verify]` |
| C | `[verify]` | `[verify]` | `[verify]` |
| D | `[verify]` | `[verify]` | `[verify]` |
| E | `[verify]` | `[verify]` | `[verify]` |
| F | `[verify]` | `[verify]` | `[verify]` |
| G | `[verify]` | `[verify]` | `[verify]` |
| H | `[verify]` | `[verify]` | `[verify]` |
| ... | `[verify]` | `[verify]` | `[verify]` |

> El **número de categorías**, los **topes diferenciados** (locaciones/servicios vs. venta de cosas
> muebles), los **parámetros** (energía, alquileres, superficie) y el **tope de exclusión** también
> se verifican contra ARCA: pueden haber cambiado. No asumir la cantidad de categorías de memoria.

---

## Recordatorios de grounding (ver `docs/GROUNDING.md`)

- Recategorización: **semestral** — confirmar el período y la fecha de vigencia de la tabla.
- Este recurso es Tier A **solo a su fecha de corte**; vencida, es `[verify]`.
- Marco normativo: Ley 24.977 y sus modificatorias + RG de ARCA que fija los valores. La cita de la
  RG vigente se verifica con el connector `boletin_nacional` / `infoleg`.
- **Toda liquidación o recategorización es un borrador para revisión de un contador matriculado.**
