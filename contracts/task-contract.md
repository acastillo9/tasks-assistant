# Contrato de tarea

Un contrato es el único input confiable del flujo. Lo escribe un humano, no el agente. El builder no lo edita; el verifier lo usa como fuente de verdad.

## Reglas

1. **Criterios verificables.** Cada criterio tiene un id y una evidencia: `test`, `diff`, `artifact` o `manual`. Si no se puede verificar, no es un criterio.
2. **Comandos exactos.** Los checks son comandos que corren en la worktree del builder, sin intervención de un LLM. Si un comando no existe, se falla; no se inventa.
3. **Scope explícito.** `paths_allow` y `paths_deny` en globs. Todo lo demás está prohibido.
4. **Presupuesto cerrado.** `max_attempts` entre 1 y 5. Dos es el default sano; tres es el techo.
5. **Modelos distintos.** `builder` y `verifier` no pueden ser el mismo par proveedor/modelo. El CLI falla si lo son.
6. **Sin secretos.** El contrato se commitea. Nada de keys, tokens ni rutas privadas.

## Flujo

```
Intake (humano escribe el contrato)
  → Plan (planner, sin código, aprobación humana)
  → Build (builder barato, worktree)
  → Verify (checks deterministas → verifier con otro modelo)
  → Human Gate (diff + evidencia + costo)
  → Done
```

Si Verify falla, el humano devuelve a Build. El contador de intentos vive en `runs/ledger.jsonl`; al superar `max_attempts`, se escala.

## Estructura mínima

```yaml
id: mi-tarea
title: "Una frase"
objective: "Qué debe lograrse."
acceptance:
  - id: A1
    criterion: "El endpoint responde 200 con el payload X."
    evidence: test
no_goals:
  - "No tocar autenticación."
scope:
  paths_allow: ["src/**", "test/**"]
  paths_deny: [".github/**"]
checks:
  - name: tests
    run: "npm test"
    timeout_s: 300
models:
  builder: { provider: deepseek, model: deepseek-chat }
  verifier: { provider: openrouter, model: anthropic/claude-sonnet-4.5 }
budget:
  max_attempts: 2
```

El esquema completo está en `contracts/task-contract.schema.json`. Para crear uno:

```bash
assistant init --id mi-tarea --title "Una frase"
```
