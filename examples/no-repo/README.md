# Repo-less task

This example shows that `tasks-assistant` does not need Git or a repository:
it only needs a working directory and a check command.

- `check.py`: deterministic check written by a human. The agent does not edit it.
- `output.md`: artifact produced by the task.
- The contract lives in `contracts/examples/demo-no-repo.yaml`.

## Run the demo

```bash
./scripts/demo-no-repo.sh
```

The script:

1. Copies `check.py` and `output.md` to a temporary directory.
2. Generates a patch with `diff -u /dev/null output.md` (without Git).
3. Runs `check` and `verify`.
4. Shows the report.

## In Kandev

In **New Task**, choose Source **None** and a **Local** executor with a directory
(or a scratch workspace). The task ID is still the task UUID, so the real
contract is named `contracts/tasks/<uuid>.yaml`.

Because there is no `--diff-base`, the Verify step must use a patch:

```bash
diff -u /dev/null output.md > changes.diff
tasks-assistant verify ... --diff changes.diff
```

For multiple files or changes against a base, use `git diff --no-index` between
the base directory and the current directory, or `diff -ruN`.
