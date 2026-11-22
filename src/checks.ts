import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import type { CheckSpec, TaskContract } from "./contract.ts";

const MAX_CAPTURE_CHARS = 512_000;
const TAIL_CHARS = 6_000;

export type CheckResult = {
  name: string;
  run: string;
  required: boolean;
  passed: boolean;
  exitCode: number | null;
  signal: NodeJS.Signals | null;
  durationMs: number;
  timedOut: boolean;
  logPath: string;
  tail: string;
};

export type ChecksSummary = {
  taskId: string;
  attempt: number;
  startedAt: string;
  finishedAt: string;
  repo: string;
  allPassed: boolean;
  results: CheckResult[];
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

function appendCapped(current: string, chunk: string): { text: string; truncated: boolean } {
  const next = current + chunk;
  if (next.length <= MAX_CAPTURE_CHARS) return { text: next, truncated: false };
  return { text: next.slice(next.length - MAX_CAPTURE_CHARS), truncated: true };
}

export function runCheck(spec: CheckSpec, repo: string, logPath: string): Promise<CheckResult> {
  const timeoutMs = (spec.timeout_s ?? 600) * 1000;
  const started = Date.now();

  return new Promise((resolvePromise) => {
    let stdout = "";
    let stderr = "";
    let truncated = false;
    let timedOut = false;

    const child = spawn(spec.run, {
      cwd: repo,
      shell: true,
      detached: true,
      env: {
        ...process.env,
        CI: "1",
        NO_COLOR: "1",
        FORCE_COLOR: "0",
        TERM: "dumb",
      },
      stdio: ["ignore", "pipe", "pipe"],
    });

    const timer = setTimeout(() => {
      timedOut = true;
      try {
        if (child.pid) process.kill(-child.pid, "SIGKILL");
        else child.kill("SIGKILL");
      } catch {
        child.kill("SIGKILL");
      }
    }, timeoutMs);

    child.stdout.on("data", (chunk: Buffer) => {
      const next = appendCapped(stdout, chunk.toString("utf8"));
      stdout = next.text;
      truncated = truncated || next.truncated;
    });
    child.stderr.on("data", (chunk: Buffer) => {
      const next = appendCapped(stderr, chunk.toString("utf8"));
      stderr = next.text;
      truncated = truncated || next.truncated;
    });

    child.on("error", (error) => {
      clearTimeout(timer);
      const message = `[spawn error] ${error.message}`;
      const body = `$ ${spec.run}\n${message}\n`;
      writeFileSync(logPath, body);
      resolvePromise({
        name: spec.name,
        run: spec.run,
        required: spec.required !== false,
        passed: false,
        exitCode: null,
        signal: null,
        durationMs: Date.now() - started,
        timedOut: false,
        logPath,
        tail: message,
      });
    });

    child.on("close", (exitCode, signal) => {
      clearTimeout(timer);
      const durationMs = Date.now() - started;
      const header = [
        `$ ${spec.run}`,
        `cwd: ${repo}`,
        `exit: ${exitCode ?? "signal"}${signal ? ` (${signal})` : ""}`,
        `duration_ms: ${durationMs}`,
        truncated ? "capture: truncated (tail kept)" : "capture: complete",
        "",
      ].join("\n");
      const body = `${header}\n--- stdout ---\n${stdout}\n--- stderr ---\n${stderr}\n`;
      writeFileSync(logPath, body);

      const combinedTail = `${stdout}\n${stderr}`.trim();
      resolvePromise({
        name: spec.name,
        run: spec.run,
        required: spec.required !== false,
        passed: exitCode === 0,
        exitCode,
        signal,
        durationMs,
        timedOut,
        logPath,
        tail: combinedTail.length > TAIL_CHARS ? combinedTail.slice(combinedTail.length - TAIL_CHARS) : combinedTail,
      });
    });
  });
}

export async function runChecks(
  contract: TaskContract,
  options: { repo: string; attempt: number; outDir: string },
): Promise<ChecksSummary> {
  const repo = resolve(options.repo);
  const outDir = resolve(options.outDir);
  mkdirSync(outDir, { recursive: true });

  const startedAt = new Date().toISOString();
  const results: CheckResult[] = [];

  for (const [index, spec] of contract.checks.entries()) {
    const logPath = resolve(outDir, `${String(index + 1).padStart(2, "0")}-${slugify(spec.name)}.log`);
    results.push(await runCheck(spec, repo, logPath));
  }

  const summary: ChecksSummary = {
    taskId: contract.id,
    attempt: options.attempt,
    startedAt,
    finishedAt: new Date().toISOString(),
    repo,
    allPassed: results.every((result) => !result.required || result.passed),
    results,
  };

  writeFileSync(resolve(outDir, "checks.json"), `${JSON.stringify(summary, null, 2)}\n`);
  return summary;
}
