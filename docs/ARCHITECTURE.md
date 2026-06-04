# Arquitectura — MCP-Contable

> Gemelo contable de MCP-Jurídico. Calca el patrón verificado de `anthropics/claude-for-legal`.
> Última actualización: 2026-06-04.

## Visión

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Cowork / Claude Code (suscripción del usuario, $0)   │
│  Accede a carpetas locales de NU + connectors MCP            │
└───────────────────────────┬─────────────────────────────────┘
                            │ instala
┌───────────────────────────▼─────────────────────────────────┐
│  Marketplace local de plugins (.claude-plugin/marketplace)   │
│  Un plugin por especialidad contable:                        │
│  CLAUDE.md (playbook) + skills/ (SKILL.md) + .mcp.json        │
│  + estudio-contable (puerta única: triage + derivación)      │
└───────────────────────────┬─────────────────────────────────┘
                            │ usa (stdio)
┌───────────────────────────▼─────────────────────────────────┐
│  Connectors MCP (FastMCP, Python) a fuentes oficiales        │
│  Todo result envuelto por common/grounding (tier + fuente)   │
└──────────────────────────────────────────────────────────────┘
```

## Componentes

- **`plugins/`** — el "estudio contable". 1 plugin = 1 especialidad. El 90% del valor.
  - `estudio-contable` (puerta única / recepción), `impuestos-liquidaciones`, `sueldos`,
    `registracion-estados-contables`, `societario-cumplimiento`.
- **`connectors/`** — servers FastMCP (uno por fuente), capa de datos. Código en inglés.
- **`recursos/`** — estáticos versionados con fecha de corte (monotributo, calendario ARCA, RT FACPCE).
- **`managed-agents/`** — agentes recurrentes (vencimientos ARCA). Plantillas Claude API (no corren en Cowork).
- **`docs/`** — esta carpeta.

## Despliegue

- **Modo principal:** Claude Cowork / Claude Code en la PC de NU.
- **Motor de IA:** la suscripción Claude del propio usuario (costo IA $0).
- **Acceso a datos:** carpetas locales (facturas, papeles de trabajo, DDJJ) + connectors MCP.
- **Instalación:** marketplace local (`/plugin marketplace add <ruta>`), igual que el oficial de Anthropic.

## Rutas (lección heredada de MCP-Jurídico)

- Los `.mcp.json` de cada plugin usan **rutas ABSOLUTAS** a `D:\git\MCP-Contable\connectors`
  (las relativas se rompen al instalar el plugin). Llevan un `$comment` que avisa que son
  específicas de la máquina.
- Las **rutas de las carpetas de datos de NU** NO van en el repo: las captura el
  `cold-start-interview` y se guardan en el perfil del usuario
  (`~/.claude/plugins/config/mcp-contable/<plugin>/CLAUDE.md`). Zero-retention.

## Connector `arca` — acceso a AFIP sin manejar credenciales

NU ya tiene un microservicio **`afip-ws`** en su VPS (`D:\git\VPS_atmosfera\shared-services\afip-ws\`):
FastAPI que usa el **certificado de NU (mismo que Odoo)** con el WS `ws_sr_constancia_inscripcion`
(Padrón A5). Expone `GET /fiscal/cuit/{cuit}` y `GET /health`.

El connector `arca` de MCP-Contable es un **cliente HTTP fino** de ese microservicio (vía
`common.fetch`): no porta WSAA ni toca el certificado, que vive **solo en el VPS**. Acceso por la
red **Tailscale** (VPS = `vmi2982897` = `100.88.25.41`). La URL base se configura en `.env`
(`AFIP_WS_BASE_URL`).

> ⚠️ Plomería pendiente (Fase 1): hoy el afip-ws bindea a `127.0.0.1:8001` del VPS → hay que
> exponerlo a la interfaz Tailscale de forma segura antes de construir el connector.

## Pendientes para producción

- Exponer afip-ws a Tailscale + verificar acceso (`GET /health`).
- Prueba de instalación real del marketplace en Claude Cowork (validar rutas `.mcp.json`).
- Revisión de Diego / un contador matriculado de los playbooks.
