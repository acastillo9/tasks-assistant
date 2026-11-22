# Hermes ↔ Kandev

Hermes es el operador: recibe mensajes, crea tareas, consulta estado y manda digest. No reemplaza el gate humano.

## MCP

Kandev expone Streamable HTTP en `http://127.0.0.1:38429/mcp` (`/mcp/sse` para clientes legacy). En `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  kandev:
    url: "http://127.0.0.1:38429/mcp"
    # Si actives auth en Kandev, agrega el PAT:
    # headers:
    #   Authorization: "Bearer ${KANDEV_MCP_TOKEN}"
    timeout: 30
```

Si Hermes corre en otro contenedor/host, usa la IP privada o un túnel; nunca expongas `/mcp` a internet.

## Tools útiles

- `create_task_kandev` — crea la tarea; título ≤ 60 caracteres, contexto en `description`, repo explícito.
- `list_tasks_kandev` / `get_task_kandev` — estado y conversación.
- `move_task_kandev` — mover entre pasos (por ejemplo, aprobar el plan).
- `update_task_kandev` — prioridad y campos sin cambiar de estado.
- `list_workflows_kandev` / `list_workflow_steps_kandev` — descubrir el workflow `Gated Coding`.

La tarea creada por Hermes entra en `Intake`. El contrato lo escribe un humano; Hermes puede redactar un borrador en `description`, pero no el contrato.

## Flujos de Telegram

| Mensaje | Acción |
|---|---|
| `nueva tarea <proyecto>: <objetivo>` | `create_task_kandev` en Intake, prioridad media |
| `estado` | Lista tareas activas, paso, agente y última actualización |
| `aprueba plan <task>` | Mueve a Build solo si el plan está revisado |
| `rechaza <task> <motivo>` | Comenta y devuelve a Build |
| `digest` | Corre el prompt de `hermes/digest.md` |
| `costo` | Lee `assistant report` o las stats de Kandev |

## Digest diario

Cron de Hermes, una vez al día:

```text
Lee las tareas activas de Kandev. Para cada una reporta:
- id, título y paso actual,
- horas desde la última actividad,
- si está en Verify, el veredicto y el costo del intento,
- si superó budget.max_attempts o lleva > 24h estancada.

Formato: lista corta, sin relleno. Al final, máximo 3 acciones sugeridas.
No muevas tareas ni apruebes nada; solo reporta.
```

## Seguridad

- Hermes con permisos mínimos: crear/leer/mover tareas, no borrar workspaces ni cambiar secretos.
- Sin credenciales de producción en el contenedor de Hermes.
- Si Kandev está en la misma VPS, usa `127.0.0.1`; si no, red privada.
- Revisa el reporte de tools que Hermes carga; un MCP mal configurado puede exponer más de lo necesario.

---

*— Andi · 2026-11-22*
