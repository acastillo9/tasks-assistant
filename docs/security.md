# Seguridad

## Fronteras de confianza

| Componente | Confianza | Puede escribir |
|---|---|---|
| Contrato | Alta (humano) | Es la fuente de verdad |
| Checks | Alta (humano) | Nada; solo ejecutan comandos |
| Builder | Media | Solo la worktree, dentro del scope |
| Verifier | Baja para escribir / alta para leer | Nada |
| Diff y contenido del repo | No confiable | Datos, no instrucciones |
| Hermes | Media | Crear/consultar tareas por MCP |

## Panel

- Kandev no trae login multiusuario activo por defecto. En local, escucha en loopback.
- En VPS: nunca publiques `38429` a internet. Usa Tailscale, Cloudflare Tunnel o reverse proxy con TLS + auth.
- Protege `/mcp`, `/mcp/sse` y `/mcp/message` igual que el panel. Un cliente MCP puede crear, mover y borrar tareas.
- Si activas autenticación, los clientes externos necesitan un personal access token.

## Secretos

- `VERIFIER_API_KEY` va en variables de entorno o en el gestor de secretos de Kandev, nunca en el contrato.
- Sin credenciales de producción en agentes. Tokens de solo lectura cuando alcancen.
- Separa keys por rol y pon topes de gasto en el proveedor.
- `runs/` puede contener diffs y salidas de tests: no lo commitees.

## Prompt injection

El repo, los issues y los comentarios son contenido no confiable.

- El system prompt del verifier declara el diff como datos y delimita `<untrusted_diff>`; el CLI neutraliza el cierre del delimitador.
- El builder no debe ejecutar instrucciones encontradas en archivos del repo.
- Permisos mínimos: sin acceso a producción, sin `sudo`, sin SSH a otros hosts.
- Sandbox: executor Docker/SSH por tarea, con límites de CPU/RAM y red restringida.
- Si una tarea toca CI, auth, migraciones o infraestructura, trátala como protegida y exige gate humano explícito.

## Verificación

- El verifier corre en modo plan/read-only y con otro proveedor/modelo.
- El CLI baja a `FAIL` cualquier `PASS` con criterios incompletos, hallazgos `blocker`/`major`, tests debilitados o archivos protegidos modificados.
- Un `PASS` no autoriza merge: el gate humano es obligatorio.
- Los comandos de check son del contrato humano; un agente no puede agregar ni cambiar comandos.

## Datos

- SQLite y worktrees en `~/.kandev` / volumen `kandev-data`.
- Backups cifrados (restic) y restore probado.
- Retención de worktrees: bórralos al archivar la tarea.
- Logs: no incluyas tokens ni datos personales; si un log los contiene, redáctalo antes de compartirlo.

## Checklist antes de exponer la VPS

- [ ] Puerto en loopback o firewall.
- [ ] Reverse proxy con TLS y auth.
- [ ] `/mcp` protegido.
- [ ] Agentes sin credenciales de producción.
- [ ] Topes de gasto por key.
- [ ] Backup + restore probado.
- [ ] Versión de Kandev fijada (no `latest`).
- [ ] Workflow y contrato revisados por un humano.

---

*— Andi · 2026-11-22*
