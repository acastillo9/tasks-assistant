# Real task contracts

Every Kandev task has a **task ID** (UUID) that appears in the panel URL:

```text
http://127.0.0.1:38429/tasks/<task-id>
```

The workflow uses that ID to interpolate `{task_id}`:

```text
$TASKS_ASSISTANT_HOME/contracts/tasks/<task-id>.yaml
```

Therefore the contract file and its `id` field must be exactly that UUID.

## Real flow

1. Create the task in Kandev from the **Intake** step and attach the Git repo.
2. Copy the `task-id` from the URL.
3. Create the contract:

   ```bash
   cd ~/acastillo/tasks-assistant
   tasks-assistant init --id <task-id> --title "One sentence"
   $EDITOR contracts/tasks/<task-id>.yaml
   ```

4. Complete verifiable criteria, no-goals, scope, checks and budget.
5. Make sure the executor profile has:

   ```text
   TASKS_ASSISTANT_HOME=/Users/andres_castillo1/acastillo/tasks-assistant
   ```

6. Move the task to **Plan**, review the plan and move it to **Build**.
7. In **Verify**, the agent runs:

   ```bash
   tasks-assistant check --contract "$TASKS_ASSISTANT_HOME/contracts/tasks/<task-id>.yaml" --repo .
   tasks-assistant verify --contract "$TASKS_ASSISTANT_HOME/contracts/tasks/<task-id>.yaml" --repo . --diff-base main
   ```

8. Review `runs/<task-id>/attempt-1/verdict.json`, `checks.json` and `tasks-assistant report` at the **Human Gate**.

## Repo-less tasks

In Kandev you can create a task with Source **None** and a **Local** executor with a directory or scratch workspace. There is no `--diff-base`, so Verify must use a patch:

```bash
diff -u /dev/null file > changes.diff
tasks-assistant verify ... --diff changes.diff
```

For multiple files, use `diff -ruN` or `git diff --no-index` between a base directory and the current one.

## Example contract

```yaml
id: <task-id>
title: "Add farewell to the greetings module"
objective: "farewell(name) returns a farewell and rejects empty names."
acceptance:
  - id: A1
    criterion: "farewell('Andrés') returns 'Goodbye, Andrés!'."
    evidence: test
  - id: A2
    criterion: "farewell('') raises ValueError with message 'name required'."
    evidence: test
no_goals:
  - "Do not change the greet signature."
scope:
  paths_allow: ["src/**", "tests/**"]
  paths_deny: [".github/**", "uv.lock", "pyproject.toml"]
checks:
  - name: tests
    run: "uv run --project . pytest -q"
    timeout_s: 60
models:
  builder: { provider: deepseek, model: deepseek-chat }
  verifier: { provider: openrouter, model: anthropic/claude-sonnet-4.5 }
budget:
  max_attempts: 2
```

## Practical rule

The human writes the contract before moving the task to Plan. The agent does not edit it. If the `task-id` does not match, the Verify step fails with “could not read …” and no verifier spend occurs.
