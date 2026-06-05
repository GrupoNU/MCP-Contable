# Recursos estáticos — MCP-Contable

Datos contables/fiscales que **no tienen un connector confiable** (no hay API, o la fuente está
detrás de login, o son PDFs sueltos) y se versionan acá como **plantillas con fecha de corte**.

## Política (innegociable)

1. **Todo recurso lleva una FECHA DE CORTE explícita.** Es Tier A **solo a esa fecha**.
2. **Vencida la fecha de corte (o si está sin completar), todo valor del recurso es `[verify]`** y
   debe reconfirmarse contra la fuente oficial antes de usarlo.
3. **Nunca se completan valores "de memoria" de un LLM.** Los números/fechas se transcriben desde la
   fuente oficial con su fecha y, cuando aplica, el número de RG que los fija.
4. Al citar un recurso, mostrar siempre **fecha de corte + fuente** y marcar `[verify]` si
   corresponde. Una liquidación/alerta hecha sobre un recurso es un **borrador para revisión de un
   contador matriculado**.

> En lo fiscal, un monto/tope/vencimiento desactualizado presentado como vigente es el riesgo nº1.
> Estos recursos existen para **dar un punto de partida trazable**, no para reemplazar la
> verificación. Ver `docs/GROUNDING.md`.

## Recursos

| Archivo | Qué es | Por qué es estático (no connector) |
|---|---|---|
| `monotributo.md` | Categorías/topes/cuotas de monotributo | No está en datos abiertos; ARCA solo HTML. Cambia por IPC (semestral). |
| `calendario-vencimientos-arca.md` | Vencimientos ARCA por impuesto y terminación de CUIT | Sin recurso estructurado público; lo fija una RG anual. |
| `mapa-rt-facpce.md` | Índice de orientación de las RT de la FACPCE | FACPCE no expone API; las RT son PDFs. Su vigencia se verifica manualmente. |

## Estado

Las tres son **plantillas** (fecha de corte "SIN COMPLETAR"): la estructura está, los valores se
cargan cuando alguien los recupera de la fuente oficial con su fecha. Mientras tanto, todo es
`[verify]`. El managed-agent `vencimientos-arca` consume `calendario-vencimientos-arca.md` y **no
afirma una fecha sin un recurso fechado o una RG recuperada**.
