# assistant

Plano de control para tareas agénticas: tablero Kandev, builder OpenCode, verificación en tres capas y Hermes como operador. El brief vive en `Projects/side/panel-tareas-agentes.md` del vault.

## Estado

Validado en local el 2026-11-22:

- Kandev instalado y corriendo en `http://127.0.0.1:38429`.
- Workflow `Gated Coding` importado en el workspace default (6 pasos).
- `assistant check` corre los checks del contrato y escribe evidencia.
- `assistant verify --dry-run` arma el prompt con contrato + checks + diff.
- 12 tests del CLI en verde.

Pendiente: keys de proveedores, perfiles por rol en Kandev, VPS, MCP de Hermes y el primer task real end-to-end.

## Arquitectura

```text
Yo ── panel Kandev ──┐
  └─ Hermes (Telegram) ─┤ MCP
                        ▼
                 Kandev (SQLite, worktrees)
                 ├─ Intake      humano escribe contrato
                 ├─ Plan        planner (modelo fuerte)
                 ├─ Build       builder (modelo barato)
                 ├─ Verify      checks → verifier (otro proveedor)
                 └─ Human Gate  diff + evidencia + costo
                        │
                 runs/<task>/attempt-N/
                 ├─ 01-tests.log
                 ├─ checks.json
                 ├─ verifier-prompt.md
                 └─ verdict.json
```

## Estructura

| Ruta | Qué es |
|---|---|
| `workflows/gated-coding.yaml` | Workflow portable de Kandev (plan → build → verify → gate) |
| `contracts/task-contract.md` | Reglas del contrato de tarea |
| `contracts/task-contract.schema.json` | Esquema JSON del contrato |
| `contracts/tasks/` | Contratos reales, uno por tarea (`<task-id>.yaml`) |
| `contracts/examples/demo-greet.yaml` | Contrato de ejemplo, usado por los tests |
| `src/cli.ts` | `assistant init / check / verify / report` |
| `src/checks.ts` | Capa 1: ejecuta comandos, captura logs y timeout |
| `src/verify.ts` | Capa 2: prompt, llamada al verifier, parseo y guards |
| `verifier/prompt.md` | System prompt del verificador |
| `verifier/rubric.md` | Rúbrica de revisión |
| `hermes/` | Conexión de Hermes por MCP y digest diario |
| `compose/docker-compose.yml` | Kandev para VPS, puerto solo en loopback |
| `docs/runbook.md` | Instalación, operación, VPS, backups |
| `docs/cost-controls.md` | Presupuestos, intentos, concurrencia, ledger |
| `docs/security.md` | Fronteras de confianza y permisos |

## Quickstart local

```bash
cd ~/acastillo/assistant
npm install
npm link                 # deja el comando `assistant` en PATH

kandev start --headless  # panel en http://localhost:38429
./scripts/import-workflow.sh
```

Crear una tarea:

```bash
assistant init --id mi-tarea --title "Una frase"
$EDITOR contracts/tasks/mi-tarea.yaml
```

Correr la capa determinista contra la worktree:

```bash
assistant check --contract contracts/tasks/mi-tarea.yaml --repo ~/ruta/al/repo
```

Verificar con otro modelo (después de que los checks pasen):

```bash
export VERIFIER_BASE_URL=https://openrouter.ai/api/v1
export VERIFIER_API_KEY=...
export VERIFIER_MODEL=anthropic/claude-sonnet-4.5
assistant verify --contract contracts/tasks/mi-tarea.yaml \
  --repo ~/ruta/al/repo --diff-base main
```

Costo acumulado:

```bash
assistant report
```

## Reglas duras

1. Los checks salen del contrato escrito por un humano. El agente no los edita.
2. Si la capa 1 falla, no se llama al verifier.
3. Builder y verifier no pueden ser el mismo proveedor/modelo; el CLI falla si lo son.
4. Un `PASS` del verifier se baja a `FAIL` si falta un criterio, hay un hallazgo `blocker`/`major`, se debilitaron tests o se tocaron archivos protegidos.
5. Máximo `budget.max_attempts` (1–5; default 2). Al superarlo, escala un humano.
6. Ningún agente aprueba su propio trabajo: el merge pasa por Human Gate.

## Modelos por rol

| Rol | Perfil | Criterio |
|---|---|---|
| Planner | Frontier (Claude/GPT clase alta) | Pocas llamadas, decide el plan |
| Builder | Económico (DeepSeek/Kimi/Qwen/GLM) | Consume la mayoría de tokens |
| Verifier | Otro proveedor/modelo, modo plan | Sin escritura, sesgo distinto |
| Triage/digest | Local o económico | Volumen alto, tareas simples |

El modelo por rol se asigna en Kandev (`Settings > Agents`) sobre el perfil de cada paso. El contrato registra el par esperado; el CLI verifica que builder y verifier sean distintos. Los precios para el ledger van en `config/pricing.yaml` (copia de `config/pricing.example.yaml`).

## Hermes y VPS

- `hermes/README.md`: snippet `mcp_servers` y prompts de digest.
- `compose/docker-compose.yml`: Kandev con volumen persistente y puerto en loopback.
- `docs/runbook.md`: despliegue, reverse proxy, backups y upgrades.

## Licencias y costo

Kandev es AGPL-3.0 self-hosted. OpenCode y Hermes son open source. Este repo es tooling propio. El único costo variable son los tokens de los modelos y la VPS.

---

*— Andi · 2026-11-22*
