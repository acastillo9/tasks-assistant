# Rúbrica del verificador

## 1. Cobertura del contrato

| Pregunta | Evidencia esperada |
|---|---|
| ¿Cada criterio tiene una prueba concreta? | Nombre de test, línea de código, salida de check |
| ¿El diff implementa el objetivo, no otra cosa? | Archivos y funciones dentro de `scope.paths_allow` |
| ¿Se respetaron los no-goals? | Ausencia de cambios en áreas prohibidas |
| ¿Los archivos protegidos quedaron intactos? | `git diff --name-only` contra la lista |

## 2. Integridad de la verificación

- Tests eliminados o comentados.
- `it.skip`, `test.only`, `describe.skip` nuevos.
- Asserts reemplazados por `expect(true).toBe(true)` o equivalentes.
- Mocks que sustituyen la lógica bajo prueba.
- Timeouts subidos para esconder un test lento.
- Snapshots regenerados sin cambio funcional que lo justifique.
- Cobertura declarada pero no ejecutada (`--if-present` que no corre nada).

Si detectas cualquiera, `tests_weakened: true` y hallazgo `major` como mínimo.

## 3. Scope

- Todo archivo tocado debe caer en `paths_allow` y fuera de `paths_deny`.
- Dependencias nuevas: solo si el contrato las permite o son imprescindibles; verifica lockfile.
- Migraciones, configuración de CI, infraestructura: trátalas como protegidas salvo autorización explícita.

## 4. Seguridad

- Secretos, tokens o credenciales en el diff.
- `eval`, `new Function`, `child_process` con input no confiable.
- SQL/command injection en rutas nuevas.
- Auth desactivada, CORS abierto, permisos elevados.
- Logs con datos personales o tokens.
- Dependencias nuevas sin justificar o con scripts de instalación.

## 5. Correctitud y compatibilidad

- Errores no manejados en caminos nuevos.
- Cambios de contrato público (API, esquema, CLI) sin actualizar consumidores.
- Condiciones de borde: vacío, null, límites, concurrencia.
- Compatibilidad con el runtime y versiones declaradas.

## 6. Costo y disciplina

- El cambio es proporcional al objetivo; no hay refactor masivo escondido.
- No se agregaron dependencias o servicios innecesarios.
- El número de intentos está dentro del presupuesto.

## Regla final

Un `PASS` significa: **el contrato se cumple, los tests siguen siendo confiables y no hay riesgo blocker/major sin declarar**. Todo lo demás es `FAIL` o `NOT_VERIFIED`.
