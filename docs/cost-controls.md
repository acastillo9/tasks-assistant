# Controles de costo

Objetivo: pagar VPS + tokens, nada más. El gasto se controla en cuatro capas: política, contrato, runtime y proveedor.

## Dónde se aplica cada control

| Control | Dónde vive | ¿Automático? |
|---|---|---|
| Máximo de intentos | `budget.max_attempts` + `tasks-assistant verify` | Sí: el CLI rechaza el intento N+1 |
| Presupuesto por tarea | `budget.max_usd` | Parcial: queda en el contrato y el ledger; el corte es humano |
| Concurrencia 1–2 | Kandev / executor | Configuración manual |
| Tests antes del verifier | `tasks-assistant verify` | Sí: falla si la capa 1 no pasó |
| Contexto mínimo | `MAX_DIFF_BYTES` (200 KB) | Sí: falla en vez de truncar |
| Modelo barato por defecto | Perfil del paso `Build` | Configuración manual |
| Escalar a modelo caro | Perfil `Plan` o reintento | Humano |
| Tope de gasto por key | Panel del proveedor | Externo |
| Prompt caching | Proveedor | Configuración del proveedor |
| Ledger de costo | `runs/ledger.jsonl` | Sí, por verifier |

## Presupuesto del contrato

```yaml
budget:
  max_attempts: 2      # 1–5; el CLI bloquea el exceso
  max_minutes: 30      # objetivo operativo
  max_usd: 1           # umbral de revisión humana
```

`max_minutes` y `max_usd` no cortan una ejecución por sí solos: son el contrato que el Human Gate revisa. Si quieres corte duro, configura el límite en el proveedor y en el executor (CPU/RAM/tiempo).

## Ledger

Cada verificación agrega una línea:

```json
{
  "task_id": "mi-tarea",
  "attempt": 1,
  "builder": { "provider": "deepseek", "model": "deepseek-chat" },
  "verifier": { "provider": "openrouter", "model": "anthropic/claude-sonnet-4.5" },
  "verdict": "FAIL",
  "usage": { "prompt_tokens": 4200, "completion_tokens": 380 },
  "cost_usd": 0.0183,
  "latency_ms": 12000
}
```

El costo se calcula solo si el modelo está en `config/pricing.yaml`. Si falta, `cost_usd` es `null` y `tasks-assistant report` lo marca como `s/tarifa`. Mantén las tarifas actualizadas; el ledger es una estimación, no la factura.

El costo del builder **no** lo captura este ledger: Kandev muestra tokens por sesión. Cruza ambos en el Human Gate.

## Reglas de operación

1. Builder económico por defecto. El modelo caro solo planea o desatasca.
2. Máximo 2 intentos; el tercero lo paga un humano con su tiempo.
3. Checks primero. Un verifier LLM sobre tests rotos es dinero tirado.
4. Diff + criterios + salida de tests, no el repo completo.
5. No reintentes el mismo prompt esperando otro resultado. Cambia el plan o escala.
6. Una tarea = un objetivo. Si el diff no cabe en 200 KB, la tarea está mal partida.

## Estimación de una tarea

```
costo ≈ (tokens_plan × precio_planner)
      + (tokens_build × precio_builder)
      + (tokens_verify × precio_verifier)
      + reintentos × (build + verify)
```

Con un builder de ~$0.30/M tokens de entrada y un verifier de ~$3/M, el verifier suele costar más por llamada aunque consuma menos tokens. Por eso solo corre después de los checks.

---

*— Andi · 2026-11-22*
