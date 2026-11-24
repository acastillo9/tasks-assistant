# Task description template

Write this in the Kandev task at the **Intake** step. It replaces the old
`contracts/tasks/<task-id>.yaml`. The description is the spec; the approved plan
is the contract.

```text
Objective:
  One or two sentences. What must be true when this is done?

Acceptance:
  - [ ] A verifiable item.
  - [ ] Another verifiable item.
  - [ ] No files outside the agreed scope were touched.

Test commands:
  - `exact command that runs non-interactively in the task workspace`
  - `another exact command`

Out of scope:
  - What must not be touched.
  - Refactors, dependency changes, CI changes, secrets.

Repo/branch:
  Repository and base branch for this task.

Risk notes:
  CI, auth, migrations, infrastructure, secrets, or anything else that needs
  extra review.
```

## Rules

- Every acceptance item must be checkable by a command or by a human reading
  the diff.
- Test commands must be exact, non-interactive and fast enough for the Verify
  step. No watch mode, no prompts.
- The builder may not edit the acceptance criteria or the test commands.
- The verifier re-runs the same commands; it does not trust the builder's
  output.
- If an item cannot be verified, say so at Intake instead of weakening the
  criterion later.

## Example

```text
Objective:
  Add farewell(name) to the greetings module. It returns a farewell and rejects
  empty names.

Acceptance:
  - [ ] farewell('Andrés') returns 'Goodbye, Andrés!'.
  - [ ] farewell('') raises ValueError with message 'name required'.
  - [ ] greet(name) keeps its current behavior.
  - [ ] No files outside src/ and tests/ were touched.

Test commands:
  - `pytest -q`

Out of scope:
  - Changing the greet signature.
  - Adding dependencies.
  - Editing CI or lockfiles.

Repo/branch:
  demo-repo, base branch main.

Risk notes:
  None.
```
