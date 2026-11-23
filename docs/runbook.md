# Runbook

## 1. Requisitos

- Node.js ≥ 22.18 (el CLI usa type stripping nativo).
- Docker solo si vas a usar el executor Docker o el Kandev en contenedor.
- Git y una cuenta de proveedor de modelos con API key.
- macOS/Linux para el panel; Windows vía WSL.

El CLI del repo:

```bash
cd ~/acastillo/tasks-assistant
npm install
npm link                 # deja `tasks-assistant` y el alias `tasks` en PATH
```

## 2. Instalar Kandev

Local:

```bash
npm install -g kandev@latest
# o: brew install kdlbs/kandev/kandev
kandev start --port 38429
```

El panel queda en `http://localhost:38429`. Los datos viven en `~/.kandev` (SQLite + worktrees). En un despliegue persistente, fija una versión: `npm install -g kandev@X.Y.Z`, no `latest`.

Servicio del sistema:

```bash
kandev service install --system   # systemd/launchd
kandev service status
```

## 3. Preparar el workspace

1. Abre el panel y crea un workspace.
2. Agrega el repositorio (URL o ruta local).
3. En **Settings > Agents**, instala/verifica OpenCode y autentica el proveedor.
4. Crea tres perfiles de OpenCode, uno por rol:
   - `Planner` — modelo frontier, modo `plan`.
   - `Builder` — modelo económico, modo `build`.
   - `Verifier` — otro proveedor/modelo, modo `plan`, sin permisos de escritura.
5. En **Settings > Secrets**, guarda `VERIFIER_BASE_URL`, `VERIFIER_API_KEY`, `VERIFIER_MODEL`. No pongas credenciales de producción.

El import del workflow **no crea perfiles**. Enlaza por nombre visible + modelo + modo exactos; si no coinciden, el paso queda sin perfil y Kandev usa el agente asignado a la tarea. Así se ve en la práctica: el workflow importado puede tener `agent_profile_id` vacío hasta que asignes el perfil en la UI.

## 4. Importar el workflow

```bash
cd ~/acastillo/tasks-assistant
./scripts/import-workflow.sh
# o con workspace explícito:
./scripts/import-workflow.sh gated-coding.yaml <workspace-id>
```

Respuesta esperada: `{"created":["Gated Coding"],"skipped":[]}`. Reimportar el mismo nombre lo salta; para actualizar, borra el workflow en la UI o usa otro nombre.

Verificar que los 6 pasos existen:

```bash
sqlite3 ~/.kandev/data/kandev.db \
  "SELECT position,name FROM workflow_steps WHERE workflow_id=(SELECT id FROM workflows WHERE name='Gated Coding') ORDER BY position;"
```

## 5. Operar una tarea

1. **Intake**: crea el contrato.

   ```bash
   tasks-assistant init --id <task-id> --title "Una frase"
   $EDITOR contracts/tasks/<task-id>.yaml
   ```

   El `task-id` debe coincidir con el id de la tarea en Kandev; el workflow interpola `{task_id}` en las rutas.

2. **Plan**: mueve la tarea a `Plan`. El planner propone y guarda el plan; no escribe código. Revísalo y muévela a `Build`.

3. **Build**: el builder implementa en su worktree y commitea.

4. **Verify**: el paso corre, en orden:

   ```bash
   tasks-assistant check --contract contracts/tasks/<task-id>.yaml --repo .
   tasks-assistant verify --contract contracts/tasks/<task-id>.yaml --repo . --diff-base main
   ```

   Si `check` falla, no hay llamada al verifier.

5. **Human Gate**: revisa diff, `verdict.json`, `checks.json` y `tasks-assistant report`. Aprueba, devuelve a `Build` o escala.

6. **Done**: se archiva a los 7 días.

## 6. Evidencia y ledger

Por intento:

```
runs/<task-id>/attempt-<n>/
├── 01-tests.log
├── checks.json
├── verifier-prompt.md
└── verdict.json
```

Histórico: `runs/ledger.jsonl`. Cada línea registra tarea, intento, builder, verifier, criterios, hallazgos, tokens, costo y latencia. `tasks-assistant report` lo resume.

`runs/` está en `.gitignore`: la evidencia es operativa, no fuente de verdad. Si quieres conservarla, súbela a un bucket o inclúyela en el backup.

## 7. VPS

```bash
cd ~/acastillo/tasks-assistant
cp .env.example .env
# edita KANDEV_VERSION con un tag real y las keys
docker compose -f compose/docker-compose.yml up -d
docker compose -f compose/docker-compose.yml logs -f kandev
```

- El puerto se publica solo en `127.0.0.1:38429`. No lo abras a internet.
- Acceso remoto: Tailscale, Cloudflare Tunnel o un reverse proxy con TLS y auth. Protege también `/mcp`, `/mcp/sse` y `/mcp/message`; necesitan streaming de larga duración.
- La imagen trae `KANDEV_DOCKER_ENABLED=false`; si quieres executor Docker dentro del contenedor, monta el socket o usa un executor SSH a otra máquina (preferible).
- VPS pequeña: Kandev en la VPS y executor SSH a tu Mac o a una máquina más grande.
- Límites de concurrencia: 1–2 tareas a la vez en 2 vCPU / 4 GB.

## 8. Backups

SQLite + worktrees viven en el volumen `kandev-data` (o `~/.kandev` en local).

```bash
# Snapshot consistente: detén Kandev o usa el backup de System
docker compose -f compose/docker-compose.yml stop kandev
docker run --rm -v kandev-data:/data -v "$PWD/backups:/backup" alpine \
  tar -czf /backup/kandev-$(date +%F).tar.gz -C /data .
docker compose -f compose/docker-compose.yml start kandev

restic -r b2:bucket:kandev backup backups/
restic -r b2:bucket:kandev check
```

Prueba un restore completo al menos una vez al mes. Un backup sin restore probado no es un backup.

## 9. Upgrades

1. Lee el CHANGELOG y fija el nuevo tag.
2. Snapshot del volumen.
3. Levanta la versión nueva en un puerto alterno con un volumen desechable.
4. Verifica que el workflow importa y que una tarea de prueba corre.
5. Cambia `KANDEV_VERSION`, recrea el contenedor y conserva el snapshot hasta validar.

No dependas de Office mode (experimental).

## 10. Troubleshooting

| Síntoma | Causa probable | Acción |
|---|---|---|
| `import` devuelve `skipped` | Ya existe un workflow con ese nombre | Bórralo en la UI o usa otro nombre |
| Paso sin agente | Perfil no coincide en nombre/modelo/modo | Asígnalo en la UI; revisa `agent_profile_id` en SQLite |
| `tasks-assistant: falta --contract` | Flag omitido | `--contract contracts/tasks/<id>.yaml` |
| `no hay evidencia de checks` | No corriste `tasks-assistant check` o el intento no coincide | Corre check con el mismo `--attempt` |
| `diff excede el máximo` | Cambio demasiado grande | Parte la tarea o revisa solo los archivos del scope |
| `verificador inválido` | Builder y verifier comparten proveedor/modelo | Cambia `VERIFIER_MODEL` o el contrato |
| `proveedor verifier 401` | Key incorrecta o sin saldo | Revisa `VERIFIER_API_KEY` y el proveedor |
| `proveedor verifier 429` | Rate limit | Baja concurrencia; reintenta con backoff |
| Checks cuelgan | Comando interactivo o watch mode | Usa comandos CI (`--run`, `--watch=false`) |

## 11. Desinstalar

```bash
docker compose -f compose/docker-compose.yml down       # conserva el volumen
docker volume rm kandev-data                            # borra datos, irreversible
npm uninstall -g kandev
```

---

*— Andi · 2026-11-22*
