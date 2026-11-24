"""tasks-assistant CLI: init, check, verify and report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from .checks import ChecksSummary, run_checks
from .contract import (
    ID_RE,
    ContractError,
    ProviderRef,
    TaskContract,
    load_contract,
)
from .ledger import (
    CriteriaCounts,
    FindingsCounts,
    LedgerEntry,
    append_ledger,
    next_attempt,
    read_ledger,
    summarize_ledger,
)
from .pricing import estimate_cost, load_pricing
from .verify import (
    MAX_DIFF_BYTES,
    VerifierResponse,
    apply_guards,
    assert_distinct_roles,
    build_verifier_prompt,
    call_verifier,
    read_verifier_instructions,
)


def _cli_name() -> str:
    invoked = Path(sys.argv[0]).name
    stem = invoked.rsplit(".", 1)[0] if "." in invoked else invoked
    return stem if stem and stem not in {"cli", "__main__"} else "tasks-assistant"


CLI_NAME = _cli_name()


class CliError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _looks_like_home(path: Path) -> bool:
    return (path / "verifier" / "prompt.md").is_file() and (path / "contracts").is_dir()


def get_home() -> Path:
    """Root of the tasks-assistant repo, configurable with TASKS_ASSISTANT_HOME."""
    env_home = os.environ.get("TASKS_ASSISTANT_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()

    here = Path(__file__).resolve()
    for parent in here.parents:
        if _looks_like_home(parent):
            return parent

    cwd = Path.cwd().resolve()
    return cwd


def get_state_dir() -> Path:
    """Directory for runs/ and the ledger, configurable with TASKS_ASSISTANT_STATE_DIR."""
    env_state = os.environ.get("TASKS_ASSISTANT_STATE_DIR")
    if env_state:
        return Path(env_state).expanduser().resolve()
    return get_home() / "runs"


def get_ledger_path() -> Path:
    return get_state_dir() / "ledger.jsonl"


def get_pricing_path() -> Path:
    return get_home() / "config" / "pricing.yaml"


def get_tasks_dir() -> Path:
    return get_home() / "contracts" / "tasks"


def out(message: str = "") -> None:
    print(message)


def require_option(value: str | None, name: str) -> str:
    if not value:
        raise CliError(f"missing --{name}")
    return value


def parse_attempt(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 1:
        raise CliError(f'--attempt must be a positive integer, got "{value}"')
    return value


def _attempt_arg(value: str) -> int:
    try:
        attempt = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f'--attempt must be a positive integer, got "{value}"'
        ) from error
    if attempt < 1:
        raise argparse.ArgumentTypeError(f'--attempt must be a positive integer, got "{value}"')
    return attempt


def load_checks_summary(path: str | Path, contract: TaskContract) -> ChecksSummary:
    checks_path = Path(path)
    if not checks_path.exists():
        raise CliError(
            f'no check evidence at {checks_path}; run "{CLI_NAME} check" first'
        )

    try:
        summary = json.loads(checks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CliError(f"invalid checks.json at {checks_path}: {error}") from error

    if summary.get("taskId") != contract["id"]:
        raise CliError(
            f'check evidence is for "{summary.get("taskId")}", not "{contract["id"]}"'
        )
    return cast(ChecksSummary, summary)


def read_diff(diff: str | None, diff_base: str | None, repo: Path) -> str:
    if diff_base:
        try:
            result = subprocess.run(
                ["git", "diff", diff_base],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as error:
            raise CliError(f"git diff {diff_base} failed: {error}") from error

        if result.returncode != 0:
            raise CliError(f"git diff {diff_base} failed: {result.stderr.strip()}")

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        untracked_list = untracked.stdout.strip()
        warning = (
            f"\n\n# Untracked files (not included in the diff):\n{untracked_list}"
            if untracked_list
            else ""
        )
        return f"{result.stdout}{warning}"

    if diff == "-":
        return sys.stdin.read()
    if diff:
        return Path(diff).read_text(encoding="utf-8")
    raise CliError("pass --diff <file|-> or --diff-base <ref>")


def assert_diff_size(diff: str) -> None:
    size = len(diff.encode("utf-8"))
    if size > MAX_DIFF_BYTES:
        raise CliError(
            f"diff of {size} bytes exceeds the maximum of {MAX_DIFF_BYTES}; "
            "split the task or review only the files in scope"
        )


def print_checks(summary: ChecksSummary) -> None:
    out(f"Checks — task {summary['taskId']} · attempt {summary['attempt']}")
    out(f"Repo: {summary['repo']}")
    out("")
    for result in summary["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        required = "" if result["required"] else " (advisory)"
        seconds = f"{result['durationMs'] / 1000:.1f}"
        out(f"  {status}{required}  {result['name']}  {seconds}s  → {result['logPath']}")
    out("")
    out(
        "Result: PASS (layer 1)"
        if summary["allPassed"]
        else "Result: FAIL (layer 1) — no verifier spend"
    )


def init_contract(task_id: str, title: str, out_dir: Path) -> Path:
    if not ID_RE.fullmatch(task_id):
        raise CliError("--id must use lowercase letters, numbers and hyphens (2-64 characters)")

    path = out_dir / f"{task_id}.yaml"
    if path.exists():
        raise CliError(f"{path} already exists; not overwriting it")

    escaped_title = title.replace('"', '\\"')
    template = f"""# Task contract. Written by a human; the agent does not edit it.
id: {task_id}
title: "{escaped_title}"
objective: "One sentence: what must be achieved."
status: draft

acceptance:
  - id: A1
    criterion: "Behavior X exists and is covered by a test."
    evidence: test
  - id: A2
    criterion: "No files outside the scope were touched."
    evidence: diff

no_goals:
  - "Do not refactor unrelated code."
  - "Do not change dependencies without justification."

scope:
  repos: []
  paths_allow:
    - "src/**"
    - "tests/**"
  paths_deny:
    - ".github/**"
    - "uv.lock"
    - "pyproject.toml"

checks:
  - name: tests
    run: "uv run --project . pytest -q"
    timeout_s: 300
  - name: lint
    run: "uv run --project . ruff check ."
    timeout_s: 120
    required: false

models:
  planner:
    provider: "frontier"
    model: "define"
  builder:
    provider: "deepseek"
    model: "deepseek-chat"
  verifier:
    provider: "openrouter"
    model: "anthropic/claude-sonnet-4.5"

budget:
  max_attempts: 2
  max_minutes: 30
  max_usd: 1

protected_paths:
  - ".github/**"
  - "tests/fixtures/**"

evidence_required:
  - tests
  - diff
  - verifier_verdict
"""

    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(template, encoding="utf-8")
    return path


def _error_entry(
    *,
    contract: TaskContract,
    repo: Path,
    attempt: int,
    checks_passed: bool,
    reasons: list[str],
    verifier_ref: ProviderRef,
    not_verified: int,
) -> LedgerEntry:
    return LedgerEntry(
        ts=_utc_now(),
        task_id=contract["id"],
        attempt=attempt,
        repo=str(repo),
        checks_passed=checks_passed,
        builder=contract["models"]["builder"],
        verifier=verifier_ref,
        verdict="ERROR",
        model_verdict="ERROR",
        downgraded=False,
        downgrade_reasons=reasons,
        findings={"blocker": 0, "major": 0, "minor": 0, "nit": 0},
        criteria={"pass": 0, "fail": 0, "not_verified": not_verified},
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        cost_usd=None,
        latency_ms=0,
    )


def _build_ledger_entry(
    *,
    contract: TaskContract,
    repo: Path,
    attempt: int,
    checks: ChecksSummary,
    verifier: VerifierResponse,
    final_verdict: Literal["PASS", "FAIL"],
    model_verdict: Literal["PASS", "FAIL"],
    downgraded: bool,
    reasons: list[str],
    cost: float | None,
    actual_verifier: ProviderRef,
) -> LedgerEntry:
    findings: FindingsCounts = {"blocker": 0, "major": 0, "minor": 0, "nit": 0}
    for finding in verifier["verdict"]["findings"]:
        findings[finding["severity"]] += 1

    criteria: CriteriaCounts = {"pass": 0, "fail": 0, "not_verified": 0}
    for criterion in verifier["verdict"]["criteria"]:
        if criterion["status"] == "PASS":
            criteria["pass"] += 1
        elif criterion["status"] == "FAIL":
            criteria["fail"] += 1
        else:
            criteria["not_verified"] += 1

    return LedgerEntry(
        ts=_utc_now(),
        task_id=contract["id"],
        attempt=attempt,
        repo=str(repo),
        checks_passed=checks["allPassed"],
        builder=contract["models"]["builder"],
        verifier=actual_verifier,
        verdict=final_verdict,
        model_verdict=model_verdict,
        downgraded=downgraded,
        downgrade_reasons=reasons,
        findings=findings,
        criteria=criteria,
        usage=verifier["usage"],
        cost_usd=cost,
        latency_ms=verifier["latencyMs"],
    )


def command_check(args: argparse.Namespace) -> int:
    contract_path = require_option(args.contract, "contract")
    contract = load_contract(Path(contract_path).resolve())
    attempt = parse_attempt(args.attempt) or next_attempt(get_ledger_path(), contract["id"])

    if attempt > contract["budget"]["max_attempts"]:
        raise CliError(
            f"attempt {attempt} exceeds budget.max_attempts="
            f"{contract['budget']['max_attempts']}; escalate to a human"
        )

    repo = Path(args.repo).expanduser().resolve() if args.repo else Path.cwd().resolve()
    out_dir = get_state_dir() / contract["id"] / f"attempt-{attempt}"
    summary = run_checks(contract, repo, attempt, out_dir)
    print_checks(summary)

    if not summary["allPassed"]:
        append_ledger(
            get_ledger_path(),
            _error_entry(
                contract=contract,
                repo=repo,
                attempt=attempt,
                checks_passed=False,
                reasons=["layer 1 failed; verifier was not invoked"],
                verifier_ref=contract["models"]["verifier"],
                not_verified=len(contract["acceptance"]),
            ),
        )

    return 0 if summary["allPassed"] else 1


def command_verify(args: argparse.Namespace) -> int:
    contract_path = require_option(args.contract, "contract")
    contract = load_contract(Path(contract_path).resolve())
    repo = Path(args.repo).expanduser().resolve() if args.repo else Path.cwd().resolve()
    attempt = parse_attempt(args.attempt) or next_attempt(get_ledger_path(), contract["id"])

    if attempt > contract["budget"]["max_attempts"]:
        raise CliError(
            f"attempt {attempt} exceeds budget.max_attempts="
            f"{contract['budget']['max_attempts']}; escalate to a human"
        )

    if args.checks:
        checks_path = Path(args.checks).expanduser().resolve()
    else:
        checks_path = get_state_dir() / contract["id"] / f"attempt-{attempt}" / "checks.json"

    checks = load_checks_summary(checks_path, contract)
    if not checks["allPassed"]:
        print_checks(checks)
        raise CliError("layer 1 failed; not invoking the verifier", 1)

    diff = read_diff(args.diff, args.diff_base, repo)
    assert_diff_size(diff)

    builder = contract["models"]["builder"]
    verifier_ref = contract["models"]["verifier"]
    assert_distinct_roles(builder, verifier_ref)

    actual_verifier = ProviderRef(
        provider=os.environ.get("VERIFIER_PROVIDER") or verifier_ref["provider"],
        model=os.environ.get("VERIFIER_MODEL") or verifier_ref["model"],
    )
    assert_distinct_roles(builder, actual_verifier)

    try:
        system_prompt = read_verifier_instructions(get_home())
    except OSError as error:
        raise CliError(
            f"could not read verifier/prompt.md in {get_home()}: {error}; "
            "set TASKS_ASSISTANT_HOME"
        ) from error

    user_prompt = build_verifier_prompt(contract, diff, checks, attempt)

    if args.save_prompt:
        prompt_path = get_state_dir() / contract["id"] / f"attempt-{attempt}" / "verifier-prompt.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(
            f"# System\n\n{system_prompt}\n\n# User\n\n{user_prompt}\n",
            encoding="utf-8",
        )
        out(f"Prompt saved to {prompt_path}")

    if args.dry_run:
        out(f"Dry run — task {contract['id']}, attempt {attempt}")
        out(f"Builder: {builder['provider']}/{builder['model']}")
        out(f"Verifier: {actual_verifier['provider']}/{actual_verifier['model']}")
        out(f"Diff: {len(diff.encode('utf-8'))} bytes · prompt: {len(user_prompt)} chars")
        out("")
        out(user_prompt[:1200])
        return 0

    base_url = os.environ.get("VERIFIER_BASE_URL")
    api_key = os.environ.get("VERIFIER_API_KEY")
    if not base_url or not api_key:
        raise CliError("missing VERIFIER_BASE_URL and/or VERIFIER_API_KEY")

    try:
        verifier = call_verifier(
            base_url=base_url,
            api_key=api_key,
            model=actual_verifier["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            contract=contract,
        )
    except Exception as error:
        message = str(error)
        append_ledger(
            get_ledger_path(),
            _error_entry(
                contract=contract,
                repo=repo,
                attempt=attempt,
                checks_passed=True,
                reasons=[message],
                verifier_ref=actual_verifier,
                not_verified=len(contract["acceptance"]),
            ),
        )
        raise CliError(f"verification failed: {message}") from error

    outcome = apply_guards(verifier["verdict"])
    pricing = load_pricing(get_pricing_path())
    cost = estimate_cost(pricing, actual_verifier["model"], verifier["usage"])
    final_verdict = outcome["finalVerdict"]["verdict"]

    append_ledger(
        get_ledger_path(),
        _build_ledger_entry(
            contract=contract,
            repo=repo,
            attempt=attempt,
            checks=checks,
            verifier=verifier,
            final_verdict=final_verdict,
            model_verdict=verifier["verdict"]["verdict"],
            downgraded=outcome["downgraded"],
            reasons=outcome["downgradeReasons"],
            cost=cost,
            actual_verifier=actual_verifier,
        ),
    )

    verdict_path = get_state_dir() / contract["id"] / f"attempt-{attempt}" / "verdict.json"
    verdict_path.parent.mkdir(parents=True, exist_ok=True)
    verdict_payload = {
        "task_id": contract["id"],
        "attempt": attempt,
        "final_verdict": final_verdict,
        "downgraded": outcome["downgraded"],
        "downgrade_reasons": outcome["downgradeReasons"],
        "builder": builder,
        "verifier": actual_verifier,
        "usage": verifier["usage"],
        "cost_usd": cost,
        "verdict": outcome["finalVerdict"],
    }
    verdict_path.write_text(
        json.dumps(verdict_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    out(f"Verification — task {contract['id']} · attempt {attempt}")
    out(f"Builder:  {builder['provider']}/{builder['model']}")
    out(f"Verifier: {actual_verifier['provider']}/{actual_verifier['model']}")
    out("Checks:   PASS")
    out("")
    for criterion in outcome["finalVerdict"]["criteria"]:
        out(f"  {criterion['status'].ljust(13)} {criterion['id']} — {criterion['evidence']}")
    out("")
    out(outcome["finalVerdict"]["summary"])
    if outcome["finalVerdict"]["findings"]:
        out("")
        for finding in outcome["finalVerdict"]["findings"]:
            location = "—"
            if finding.get("file"):
                location = finding["file"]
                if finding.get("line"):
                    location += f":{finding['line']}"
            out(f"  [{finding['severity']}] {location} {finding['issue']}")
    if outcome["downgraded"]:
        out("")
        out(
            "⚠ The model said PASS but the guard downgraded it to FAIL: "
            + "; ".join(outcome["downgradeReasons"])
        )
    out("")
    out(
        f"Tokens: {verifier['usage']['prompt_tokens']} in / "
        f"{verifier['usage']['completion_tokens']} out"
    )
    out("Verifier cost: " + ("no rate configured" if cost is None else f"USD {cost:.4f}"))
    out(f"Evidence: {verdict_path}")
    out("")
    out("VERDICT: PASS (pending human gate)" if final_verdict == "PASS" else "VERDICT: FAIL")

    return 0 if final_verdict == "PASS" else 1


def command_report(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger).expanduser().resolve() if args.ledger else get_ledger_path()
    entries = read_ledger(ledger_path)

    if args.json:
        out(
            json.dumps(
                {"entries": entries, "summary": summarize_ledger(entries)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not entries:
        out(f"No records in {ledger_path}")
        return 0

    summaries = summarize_ledger(entries)
    out(f"Ledger: {ledger_path}")
    out("")
    out(
        "TASK".ljust(28)
        + "ATTEMPTS".ljust(10)
        + "LAST".ljust(10)
        + "COST USD".ljust(12)
        + "MODELS"
    )
    for summary in summaries:
        cost = f"{summary['cost_usd']:.4f}"
        if summary["unknown_cost_entries"] > 0:
            cost += f" (+{summary['unknown_cost_entries']} no-rate)"
        out(
            summary["task_id"].ljust(28)
            + str(summary["attempts"]).ljust(10)
            + summary["last_verdict"].ljust(10)
            + cost.ljust(12)
            + ", ".join(summary["models"])
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=CLI_NAME,
        description=f"{CLI_NAME} — contract, checks and verification",
        epilog=(
            "Rules:\n"
            "  - Checks come from the contract written by a human, not from the agent.\n"
            "  - The verifier does not run if layer 1 fails.\n"
            "  - Builder and verifier cannot be the same provider/model.\n"
            "  - PASS requires every criterion to be PASS and zero blocker/major findings.\n\n"
            "Variables:\n"
            "  TASKS_ASSISTANT_HOME       root of this repo (default: the CLI's own)\n"
            "  TASKS_ASSISTANT_STATE_DIR  runs/ directory (default: <home>/runs)\n"
            "  VERIFIER_BASE_URL          OpenAI-compatible endpoint\n"
            "  VERIFIER_API_KEY           verifier key\n"
            "  VERIFIER_MODEL             verifier model override\n"
            "  VERIFIER_PROVIDER          verifier provider override\n"
            "  BUILDER_PROVIDER / BUILDER_MODEL  informational for the gate"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="create a task contract")
    init_parser.add_argument("--id")
    init_parser.add_argument("--title")
    init_parser.add_argument("--out")
    init_parser.set_defaults(func=command_init)

    check_parser = subparsers.add_parser("check", help="run the deterministic checks")
    check_parser.add_argument("--contract")
    check_parser.add_argument("--repo")
    check_parser.add_argument("--attempt", type=_attempt_arg)
    check_parser.set_defaults(func=command_check)

    verify_parser = subparsers.add_parser("verify", help="verify the diff with another model")
    verify_parser.add_argument("--contract")
    verify_parser.add_argument("--repo")
    verify_parser.add_argument("--checks")
    verify_parser.add_argument("--diff")
    verify_parser.add_argument("--diff-base", dest="diff_base")
    verify_parser.add_argument("--attempt", type=_attempt_arg)
    verify_parser.add_argument("--dry-run", action="store_true")
    verify_parser.add_argument("--save-prompt", action="store_true")
    verify_parser.set_defaults(func=command_verify)

    report_parser = subparsers.add_parser("report", help="summarize the cost ledger")
    report_parser.add_argument("--ledger")
    report_parser.add_argument("--json", action="store_true")
    report_parser.set_defaults(func=command_report)

    return parser


def command_init(args: argparse.Namespace) -> int:
    task_id = require_option(args.id, "id")
    title = require_option(args.title, "title")
    out_dir = Path(args.out).expanduser().resolve() if args.out else get_tasks_dir()
    path = init_contract(task_id, title, out_dir)
    out(f"Contract created: {path}")
    out("Complete criteria, scope and test commands before moving it to Kandev.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()

    if args_list and args_list[0] == "help":
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(args_list)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2

    if args.command is None:
        parser.print_help()
        return 0

    try:
        return int(args.func(args))
    except CliError as error:
        print(f"{CLI_NAME}: {error}", file=sys.stderr)
        return error.exit_code
    except ContractError as error:
        print(f"{CLI_NAME}: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"{CLI_NAME}: {error}", file=sys.stderr)
        return 2
