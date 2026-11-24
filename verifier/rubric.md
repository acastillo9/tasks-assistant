# Verifier rubric

## 1. Contract coverage

| Question | Expected evidence |
|---|---|
| Does every criterion have concrete proof? | Test name, code line, check output |
| Does the diff implement the objective, and nothing else? | Files and functions within `scope.paths_allow` |
| Were the no-goals respected? | No changes in prohibited areas |
| Were protected files left untouched? | `git diff --name-only` against the list |

## 2. Verification integrity

- Deleted or commented-out tests.
- New `pytest.mark.skip`, `pytest.skip()` or `pytest.mark.xfail`.
- Asserts replaced with `assert True` or equivalents.
- Mocks that replace the logic under test.
- Timeouts raised to hide a slow test.
- Snapshots regenerated with no functional change to justify it.
- Coverage claimed but not executed (`-k` that selects nothing).

If you detect any of these, set `tests_weakened: true` and raise at least a `major` finding.

## 3. Scope

- Every touched file must fall within `paths_allow` and outside `paths_deny`.
- New dependencies: only if the contract allows them or they are essential; verify the lockfile.
- Migrations, CI configuration, infrastructure: treat them as protected unless explicitly authorized.

## 4. Security

- Secrets, tokens or credentials in the diff.
- `eval`, `exec`, `subprocess` with untrusted input.
- SQL/command injection in new paths.
- Disabled auth, open CORS, elevated permissions.
- Logs containing personal data or tokens.
- Unjustified new dependencies or ones with install scripts.

## 5. Correctness and compatibility

- Unhandled errors in new paths.
- Public contract changes (API, schema, CLI) without updating consumers.
- Edge cases: empty, null, limits, concurrency.
- Compatibility with the declared runtime and versions.

## 6. Cost and discipline

- The change is proportional to the objective; there is no hidden massive refactor.
- No unnecessary dependencies or services were added.
- The number of attempts is within budget.

## Final rule

A `PASS` means: **the contract is met, tests are still trustworthy and there is no undeclared blocker/major risk**. Everything else is `FAIL` or `NOT_VERIFIED`.
