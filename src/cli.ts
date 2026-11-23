#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { ContractError, contractAsYaml, loadContract, type TaskContract } from "./contract.ts";
import { runChecks, type ChecksSummary } from "./checks.ts";
import { appendLedger, nextAttempt, readLedger, summarizeLedger, type LedgerEntry } from "./ledger.ts";
import { estimateCost, loadPricing } from "./pricing.ts";
import {
  MAX_DIFF_BYTES,
  applyGuards,
  assertDistinctRoles,
  buildVerifierPrompt,
  callVerifier,
  readVerifierInstructions,
  type VerifierResponse,
} from "./verify.ts";

const TASKS_ASSISTANT_HOME = process.env.TASKS_ASSISTANT_HOME
  ? resolve(process.env.TASKS_ASSISTANT_HOME)
  : resolve(dirname(fileURLToPath(import.meta.url)), "..");

const CLI_NAME = (() => {
  const invoked = basename(process.argv[1] ?? "").replace(/\.[^.]+$/, "");
  return invoked && invoked !== "cli" ? invoked : "tasks-assistant";
})();

const LEDGER_PATH = resolve(TASKS_ASSISTANT_HOME, "runs", "ledger.jsonl");
const PRICING_PATH = resolve(TASKS_ASSISTANT_HOME, "config", "pricing.yaml");

class CliError extends Error {
  readonly exitCode: number;

  constructor(message: string, exitCode = 2) {
    super(message);
    this.name = "CliError";
    this.exitCode = exitCode;
  }
}

function out(message = ""): void {
  process.stdout.write(`${message}\n`);
}

function requireOption(value: string | undefined, name: string): string {
  if (!value) throw new CliError(`falta --${name}`);
  return value;
}

function parseAttempt(value: string | boolean | undefined): number | undefined {
  if (value === undefined) return undefined;
  const attempt = Number(value);
  if (!Number.isInteger(attempt) || attempt < 1) {
    throw new CliError(`--attempt debe ser un entero positivo, recibí "${value}"`);
  }
  return attempt;
}

function loadChecksSummary(path: string, contract: TaskContract): ChecksSummary {
  if (!existsSync(path)) {
    throw new CliError(`no hay evidencia de checks en ${path}; corre "${CLI_NAME} check" primero`);
  }
  const summary = JSON.parse(readFileSync(path, "utf8")) as ChecksSummary;
  if (summary.taskId !== contract.id) {
    throw new CliError(`la evidencia de checks es de "${summary.taskId}", no de "${contract.id}"`);
  }
  return summary;
}

function readDiff(options: { diff?: string; diffBase?: string; repo: string }): string {
  if (options.diffBase) {
    const result = spawnSync("git", ["diff", options.diffBase], {
      cwd: options.repo,
      encoding: "utf8",
      maxBuffer: 20 * 1024 * 1024,
    });
    if (result.status !== 0) {
      throw new CliError(`git diff ${options.diffBase} falló: ${(result.stderr || "").trim()}`);
    }
    const untracked = spawnSync("git", ["ls-files", "--others", "--exclude-standard"], {
      cwd: options.repo,
      encoding: "utf8",
    });
    const untrackedList = (untracked.stdout || "").trim();
    const warning = untrackedList
      ? `\n\n# Archivos sin trackear (no incluidos en el diff):\n${untrackedList}`
      : "";
    return `${result.stdout}${warning}`;
  }

  if (options.diff === "-") return readFileSync(0, "utf8");
  if (options.diff) return readFileSync(options.diff, "utf8");
  throw new CliError("pasa --diff <archivo|-> o --diff-base <ref>");
}

function assertDiffSize(diff: string): void {
  const bytes = Buffer.byteLength(diff, "utf8");
  if (bytes > MAX_DIFF_BYTES) {
    throw new CliError(
      `diff de ${bytes} bytes excede el máximo de ${MAX_DIFF_BYTES}; parte la tarea o revisa solo los archivos del scope`,
    );
  }
}

function printChecks(summary: ChecksSummary): void {
  out(`Checks — tarea ${summary.taskId} · intento ${summary.attempt}`);
  out(`Repo: ${summary.repo}`);
  out("");
  for (const result of summary.results) {
    const status = result.passed ? "PASS" : "FAIL";
    const required = result.required ? "" : " (advisory)";
    const seconds = (result.durationMs / 1000).toFixed(1);
    out(`  ${status}${required}  ${result.name}  ${seconds}s  → ${result.logPath}`);
  }
  out("");
  out(summary.allPassed ? "Resultado: PASS (capa 1)" : "Resultado: FAIL (capa 1) — no se gasta en verifier");
}

function initContract(options: { id: string; title: string; outDir: string }): string {
  if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(options.id)) {
    throw new CliError("--id debe usar minúsculas, números y guiones (2-64 caracteres)");
  }
  const path = resolve(options.outDir, `${options.id}.yaml`);
  if (existsSync(path)) throw new CliError(`ya existe ${path}; no lo sobreescribo`);

  const template = `# Contrato de tarea. Escrito por un humano; el agente no lo edita.
id: ${options.id}
title: "${options.title.replaceAll('"', '\\"')}"
objective: "Una frase: qué debe lograrse."
status: draft

acceptance:
  - id: A1
    criterion: "El comportamiento X existe y está cubierto por un test."
    evidence: test
  - id: A2
    criterion: "No se tocaron archivos fuera del scope."
    evidence: diff

no_goals:
  - "No refactorizar código no relacionado."
  - "No cambiar dependencias sin justificarlo."

scope:
  repos: []
  paths_allow:
    - "src/**"
    - "test/**"
  paths_deny:
    - ".github/**"
    - "package-lock.json"

checks:
  - name: tests
    run: "npm test"
    timeout_s: 300
  - name: typecheck
    run: "npm run typecheck --if-present"
    timeout_s: 120
    required: false

models:
  planner:
    provider: "frontier"
    model: "definir"
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
  - "test/fixtures/**"

evidence_required:
  - tests
  - diff
  - verifier_verdict
`;

  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, template);
  return path;
}

function verdictForError(reason: string): LedgerEntry["verdict"] {
  return "ERROR";
}

function buildLedgerEntry(options: {
  contract: TaskContract;
  repo: string;
  attempt: number;
  checks: ChecksSummary;
  verifier: VerifierResponse;
  finalVerdict: "PASS" | "FAIL";
  modelVerdict: "PASS" | "FAIL";
  downgraded: boolean;
  reasons: string[];
  cost: number | null;
  actualVerifier: { provider: string; model: string };
}): LedgerEntry {
  const findings = { blocker: 0, major: 0, minor: 0, nit: 0 };
  for (const finding of options.verifier.verdict.findings) findings[finding.severity] += 1;

  const criteria = { pass: 0, fail: 0, not_verified: 0 };
  for (const criterion of options.verifier.verdict.criteria) {
    if (criterion.status === "PASS") criteria.pass += 1;
    else if (criterion.status === "FAIL") criteria.fail += 1;
    else criteria.not_verified += 1;
  }

  return {
    ts: new Date().toISOString(),
    task_id: options.contract.id,
    attempt: options.attempt,
    repo: options.repo,
    checks_passed: options.checks.allPassed,
    builder: {
      provider: options.contract.models.builder.provider,
      model: options.contract.models.builder.model,
    },
    verifier: options.actualVerifier,
    verdict: options.finalVerdict,
    model_verdict: options.modelVerdict,
    downgraded: options.downgraded,
    downgrade_reasons: options.reasons,
    findings,
    criteria,
    usage: options.verifier.usage,
    cost_usd: options.cost,
    latency_ms: options.verifier.latencyMs,
  };
}

async function commandVerify(values: Record<string, string | boolean | undefined>): Promise<number> {
  const contractPath = requireOption(values.contract as string | undefined, "contract");
  const contract = loadContract(resolve(contractPath));
  const repo = resolve((values.repo as string | undefined) ?? process.cwd());
  const attempt = parseAttempt(values.attempt) ?? nextAttempt(LEDGER_PATH, contract.id);

  if (attempt > contract.budget.max_attempts) {
    throw new CliError(
      `intento ${attempt} excede budget.max_attempts=${contract.budget.max_attempts}; escala a un humano`,
    );
  }

  const checksPath = resolve(
    (values.checks as string | undefined) ?? resolve(TASKS_ASSISTANT_HOME, "runs", contract.id, `attempt-${attempt}`, "checks.json"),
  );
  const checks = loadChecksSummary(checksPath, contract);
  if (!checks.allPassed) {
    printChecks(checks);
    throw new CliError("la capa 1 falló; no se invoca al verifier", 1);
  }

  const diff = readDiff({
    diff: values.diff as string | undefined,
    diffBase: values["diff-base"] as string | undefined,
    repo,
  });
  assertDiffSize(diff);

  const builder = contract.models.builder;
  const verifierRef = contract.models.verifier;
  assertDistinctRoles(builder, verifierRef);

  const envModel = process.env.VERIFIER_MODEL;
  const actualVerifier = {
    provider: process.env.VERIFIER_PROVIDER ?? verifierRef.provider,
    model: envModel ?? verifierRef.model,
  };
  assertDistinctRoles(builder, actualVerifier);

  const systemPrompt = readVerifierInstructions(TASKS_ASSISTANT_HOME);
  const userPrompt = buildVerifierPrompt({ contract, diff, checksSummary: checks, attempt });

  if (values["save-prompt"]) {
    const promptPath = resolve(TASKS_ASSISTANT_HOME, "runs", contract.id, `attempt-${attempt}`, "verifier-prompt.md");
    mkdirSync(dirname(promptPath), { recursive: true });
    writeFileSync(promptPath, `# System\n\n${systemPrompt}\n\n# User\n\n${userPrompt}\n`);
    out(`Prompt guardado en ${promptPath}`);
  }

  if (values["dry-run"]) {
    out(`Dry run — tarea ${contract.id}, intento ${attempt}`);
    out(`Builder: ${builder.provider}/${builder.model}`);
    out(`Verifier: ${actualVerifier.provider}/${actualVerifier.model}`);
    out(`Diff: ${Buffer.byteLength(diff, "utf8")} bytes · prompt: ${userPrompt.length} chars`);
    out("");
    out(userPrompt.slice(0, 1200));
    return 0;
  }

  const baseUrl = process.env.VERIFIER_BASE_URL;
  const apiKey = process.env.VERIFIER_API_KEY;
  if (!baseUrl || !apiKey) {
    throw new CliError("faltan VERIFIER_BASE_URL y/o VERIFIER_API_KEY");
  }

  let verifier: VerifierResponse;
  try {
    verifier = await callVerifier({
      baseUrl,
      apiKey,
      model: actualVerifier.model,
      systemPrompt,
      userPrompt,
      contract,
    });
  } catch (error) {
    const message = (error as Error).message;
    appendLedger(LEDGER_PATH, {
      ts: new Date().toISOString(),
      task_id: contract.id,
      attempt,
      repo,
      checks_passed: true,
      builder,
      verifier: actualVerifier,
      verdict: verdictForError(message),
      model_verdict: verdictForError(message),
      downgraded: false,
      downgrade_reasons: [message],
      findings: { blocker: 0, major: 0, minor: 0, nit: 0 },
      criteria: { pass: 0, fail: 0, not_verified: contract.acceptance.length },
      usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      cost_usd: null,
      latency_ms: 0,
    });
    throw new CliError(`verificación falló: ${message}`);
  }

  const outcome = applyGuards(verifier.verdict);
  const pricing = loadPricing(PRICING_PATH);
  const cost = estimateCost(pricing, actualVerifier.model, verifier.usage);
  const finalVerdict = outcome.finalVerdict.verdict;

  const entry = buildLedgerEntry({
    contract,
    repo,
    attempt,
    checks,
    verifier,
    finalVerdict,
    modelVerdict: verifier.verdict.verdict,
    downgraded: outcome.downgraded,
    reasons: outcome.downgradeReasons,
    cost,
    actualVerifier,
  });
  appendLedger(LEDGER_PATH, entry);

  const verdictPath = resolve(TASKS_ASSISTANT_HOME, "runs", contract.id, `attempt-${attempt}`, "verdict.json");
  mkdirSync(dirname(verdictPath), { recursive: true });
  writeFileSync(
    verdictPath,
    `${JSON.stringify(
      {
        task_id: contract.id,
        attempt,
        final_verdict: finalVerdict,
        downgraded: outcome.downgraded,
        downgrade_reasons: outcome.downgradeReasons,
        builder,
        verifier: actualVerifier,
        usage: verifier.usage,
        cost_usd: cost,
        verdict: outcome.finalVerdict,
      },
      null,
      2,
    )}\n`,
  );

  out(`Verificación — tarea ${contract.id} · intento ${attempt}`);
  out(`Builder:  ${builder.provider}/${builder.model}`);
  out(`Verifier: ${actualVerifier.provider}/${actualVerifier.model}`);
  out(`Checks:   PASS`);
  out("");
  for (const criterion of outcome.finalVerdict.criteria) {
    out(`  ${criterion.status.padEnd(13)} ${criterion.id} — ${criterion.evidence}`);
  }
  out("");
  out(outcome.finalVerdict.summary);
  if (outcome.finalVerdict.findings.length > 0) {
    out("");
    for (const finding of outcome.finalVerdict.findings) {
      const location = finding.file ? `${finding.file}${finding.line ? `:${finding.line}` : ""}` : "—";
      out(`  [${finding.severity}] ${location} ${finding.issue}`);
    }
  }
  if (outcome.downgraded) {
    out("");
    out(`⚠ El modelo dijo PASS pero el guard lo bajó a FAIL: ${outcome.downgradeReasons.join("; ")}`);
  }
  out("");
  out(`Tokens: ${verifier.usage.prompt_tokens} in / ${verifier.usage.completion_tokens} out`);
  out(`Costo verifier: ${cost === null ? "sin tarifa configurada" : `USD ${cost.toFixed(4)}`}`);
  out(`Evidencia: ${verdictPath}`);
  out("");
  out(finalVerdict === "PASS" ? "VEREDICTO: PASS (pendiente gate humano)" : "VEREDICTO: FAIL");

  return finalVerdict === "PASS" ? 0 : 1;
}

function commandReport(values: Record<string, string | boolean | undefined>): number {
  const ledgerPath = resolve((values.ledger as string | undefined) ?? LEDGER_PATH);
  const entries = readLedger(ledgerPath);

  if (values.json) {
    out(JSON.stringify({ entries, summary: summarizeLedger(entries) }, null, 2));
    return 0;
  }

  if (entries.length === 0) {
    out(`Sin registros en ${ledgerPath}`);
    return 0;
  }

  const summaries = summarizeLedger(entries);
  out(`Ledger: ${ledgerPath}`);
  out("");
  out("TAREA".padEnd(28) + "INTENTOS".padEnd(10) + "ÚLTIMO".padEnd(10) + "COSTO USD".padEnd(12) + "MODELOS");
  for (const summary of summaries) {
    const cost = summary.unknown_cost_entries > 0
      ? `${summary.cost_usd.toFixed(4)} (+${summary.unknown_cost_entries} s/tarifa)`
      : summary.cost_usd.toFixed(4);
    out(
      summary.task_id.padEnd(28) +
        String(summary.attempts).padEnd(10) +
        summary.last_verdict.padEnd(10) +
        cost.padEnd(12) +
        summary.models.join(", "),
    );
  }
  return 0;
}

async function main(): Promise<number> {
  const { values, positionals } = parseArgs({
    args: process.argv.slice(2),
    allowPositionals: true,
    options: {
      contract: { type: "string" },
      repo: { type: "string" },
      out: { type: "string" },
      checks: { type: "string" },
      diff: { type: "string" },
      "diff-base": { type: "string" },
      attempt: { type: "string" },
      ledger: { type: "string" },
      id: { type: "string" },
      title: { type: "string" },
      json: { type: "boolean" },
      "dry-run": { type: "boolean" },
      "save-prompt": { type: "boolean" },
      help: { type: "boolean", short: "h" },
    },
  });

  const command = positionals[0];

  if (!command || values.help || command === "help") {
    out(`${CLI_NAME} — contrato, checks y verificación

Uso:
  ${CLI_NAME} init --id <slug> --title <título> [--out contracts/tasks]
  ${CLI_NAME} check --contract <archivo> [--repo <dir>] [--attempt <n>]
  ${CLI_NAME} verify --contract <archivo> --repo <dir> (--diff <archivo|-> | --diff-base <ref>)
                   [--attempt <n>] [--dry-run] [--save-prompt]
  ${CLI_NAME} report [--ledger <archivo>] [--json]

Reglas:
  - Los checks salen del contrato escrito por un humano, no del agente.
  - El verifier no corre si la capa 1 falla.
  - Builder y verifier no pueden ser el mismo provider/model.
  - PASS exige todos los criterios en PASS y cero hallazgos blocker/major.

Variables:
  TASKS_ASSISTANT_HOME       raíz de este repo (default: la del CLI)
  VERIFIER_BASE_URL    endpoint OpenAI-compatible
  VERIFIER_API_KEY     key del verifier
  VERIFIER_MODEL       override del modelo verifier
  VERIFIER_PROVIDER    override del proveedor verifier
  BUILDER_PROVIDER / BUILDER_MODEL  informativos para el gate`);
    return 0;
  }

  switch (command) {
    case "init": {
      const id = requireOption(values.id as string | undefined, "id");
      const title = requireOption(values.title as string | undefined, "title");
      const path = initContract({
        id,
        title,
        outDir: resolve((values.out as string | undefined) ?? resolve(TASKS_ASSISTANT_HOME, "contracts", "tasks")),
      });
      out(`Contrato creado: ${path}`);
      out("Completa criterios, scope y comandos de test antes de pasarlo a Kandev.");
      return 0;
    }

    case "check": {
      const contractPath = requireOption(values.contract as string | undefined, "contract");
      const contract = loadContract(resolve(contractPath));
      const attempt = parseAttempt(values.attempt) ?? nextAttempt(LEDGER_PATH, contract.id);

      if (attempt > contract.budget.max_attempts) {
        throw new CliError(
          `intento ${attempt} excede budget.max_attempts=${contract.budget.max_attempts}; escala a un humano`,
        );
      }

      const repo = resolve((values.repo as string | undefined) ?? process.cwd());
      const outDir = resolve(TASKS_ASSISTANT_HOME, "runs", contract.id, `attempt-${attempt}`);
      const summary = await runChecks(contract, { repo, attempt, outDir });
      printChecks(summary);

      if (!summary.allPassed) {
        appendLedger(LEDGER_PATH, {
          ts: new Date().toISOString(),
          task_id: contract.id,
          attempt,
          repo,
          checks_passed: false,
          builder: contract.models.builder,
          verifier: contract.models.verifier,
          verdict: "ERROR",
          model_verdict: "ERROR",
          downgraded: false,
          downgrade_reasons: ["capa 1 falló; no se invocó al verifier"],
          findings: { blocker: 0, major: 0, minor: 0, nit: 0 },
          criteria: { pass: 0, fail: 0, not_verified: contract.acceptance.length },
          usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
          cost_usd: null,
          latency_ms: 0,
        });
      }

      return summary.allPassed ? 0 : 1;
    }

    case "verify":
      return commandVerify(values);

    case "report":
      return commandReport(values);

    default:
      throw new CliError(`comando desconocido: ${command}`);
  }
}

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    const exitCode = error instanceof CliError ? error.exitCode : 2;
    const message = error instanceof ContractError || error instanceof Error ? error.message : String(error);
    process.stderr.write(`${CLI_NAME}: ${message}\n`);
    process.exit(exitCode);
  });
