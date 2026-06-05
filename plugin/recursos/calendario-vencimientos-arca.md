# Recurso estático — Calendario de vencimientos ARCA

> ⚠️ **RECURSO ESTÁTICO CON FECHA DE CORTE — Tier A solo a la fecha de captura.**
> **Año fiscal:** `[SIN COMPLETAR]` · **Fecha de corte:** `[SIN COMPLETAR — este recurso es una PLANTILLA]`
> **Fuente oficial:** ARCA (ex-AFIP) — calendario de vencimientos. https://www.arca.gob.ar
> **RG de ARCA que fija el calendario del año:** `[verify]`
>
> 🚨 **Los vencimientos ARCA cambian cada año por RG y pueden corregirse durante el año.** Por eso:
> - **Mientras "Fecha de corte" diga "SIN COMPLETAR", este archivo NO contiene fechas válidas.**
> - Aun completo, **toda fecha es `[verify]`**: reconfirmar contra ARCA / la RG vigente antes de
>   usarla para presentar o pagar. Un vencimiento perdido tiene consecuencias (intereses, multas).
> - **Este recurso NO reemplaza la verificación contra ARCA.** Es un punto de partida fechado.

---

## Cómo se usa este recurso

1. Para **completarlo**: recuperar el cronograma del año desde ARCA (o la RG que lo fija), transcribir
   las fechas por impuesto y terminación de CUIT, y anotar **año, fecha de corte y número de RG**.
2. Para **usarlo**: leer solo si la fecha de corte es del año fiscal en curso. Mostrar siempre la
   fecha y la fuente. Para una fecha puntual que se va a usar para presentar/pagar → **`[verify]`**.
3. **Nunca** completar fechas "de memoria": el calendario lo fija ARCA por RG cada año.

---

## Estructura (PLANTILLA — completar desde ARCA con fecha)

> Los vencimientos generales suelen ordenarse por **terminación de CUIT** (0-1, 2-3, 4-5, 6-7, 8-9) y
> por impuesto/régimen. Esta estructura es de referencia; las fechas se completan desde ARCA.

### IVA (DDJJ y pago mensual)
| Terminación CUIT | Vencimiento DDJJ | Vencimiento pago |
|---|---|---|
| 0-1 | `[verify]` | `[verify]` |
| 2-3 | `[verify]` | `[verify]` |
| 4-5 | `[verify]` | `[verify]` |
| 6-7 | `[verify]` | `[verify]` |
| 8-9 | `[verify]` | `[verify]` |

### Seguridad social — F.931 (mensual)
| Terminación CUIT | Vencimiento presentación | Vencimiento pago |
|---|---|---|
| 0-9 | `[verify]` | `[verify]` |

### Ganancias y Bienes Personales (anual — personas humanas / sociedades)
| Concepto | Vencimiento |
|---|---|
| Ganancias sociedades (según cierre de ejercicio) | `[verify]` |
| Ganancias / Bienes Personales personas humanas | `[verify]` |

### Monotributo
| Concepto | Vencimiento |
|---|---|
| Pago de la cuota mensual | `[verify]` |
| Recategorización semestral | `[verify]` |

> Otros regímenes (retenciones/percepciones — SICORE/SIRE, regímenes de información) tienen su propio
> cronograma: verificar cada uno contra ARCA. **No asumir** que comparten fecha.

---

## Recordatorios de grounding

- Este recurso es Tier A **solo a su fecha de corte / año fiscal**; fuera de eso es `[verify]`.
- El connector `santafe_fiscal` da el **calendario de Ingresos Brutos de Santa Fe** (provincial,
  aparte de este, que es nacional/ARCA).
- Lo consume el managed-agent `vencimientos-arca` (ver `managed-agents/`), que **nunca afirma una
  fecha sin este recurso fechado o una RG recuperada**, y marca todo como lead a verificar.
- **Toda alerta de vencimiento es un borrador para revisión de un contador matriculado.**
