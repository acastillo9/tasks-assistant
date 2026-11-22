import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import type { Usage } from "./verify.ts";

export type LedgerEntry = {
  ts: string;
  task_id: string;
  attempt: number;
  repo: string;
  checks_passed: boolean;
  builder: { provider: string; model: string };
  verifier: { provider: string; model: string };
  verdict: "PASS" | "FAIL" | "ERROR";
  model_verdict: "PASS" | "FAIL" | "ERROR";
  downgraded: boolean;
  downgrade_reasons: string[];
  findings: { blocker: number; major: number; minor: number; nit: number };
  criteria: { pass: number; fail: number; not_verified: number };
  usage: Usage;
  cost_usd: number | null;
  latency_ms: number;
};

export function readLedger(file: string): LedgerEntry[] {
  if (!existsSync(file)) return [];
  return readFileSync(file, "utf8")
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line, index) => {
      try {
        return JSON.parse(line) as LedgerEntry;
      } catch {
        throw new Error(`ledger inválido en ${file}, línea ${index + 1}`);
      }
    });
}

export function appendLedger(file: string, entry: LedgerEntry): void {
  mkdirSync(dirname(file), { recursive: true });
  appendFileSync(file, `${JSON.stringify(entry)}\n`);
}

export function nextAttempt(file: string, taskId: string): number {
  const previous = readLedger(file).filter((entry) => entry.task_id === taskId);
  return previous.length + 1;
}

export type TaskSummary = {
  task_id: string;
  attempts: number;
  last_verdict: LedgerEntry["verdict"];
  last_ts: string;
  cost_usd: number;
  unknown_cost_entries: number;
  models: string[];
};

export function summarizeLedger(entries: LedgerEntry[]): TaskSummary[] {
  const byTask = new Map<string, LedgerEntry[]>();
  for (const entry of entries) {
    const list = byTask.get(entry.task_id) ?? [];
    list.push(entry);
    byTask.set(entry.task_id, list);
  }

  return [...byTask.entries()]
    .map(([taskId, list]) => {
      const sorted = [...list].sort((a, b) => a.ts.localeCompare(b.ts));
      const last = sorted[sorted.length - 1];
      const known = sorted.filter((entry) => entry.cost_usd !== null);
      return {
        task_id: taskId,
        attempts: sorted.length,
        last_verdict: last.verdict,
        last_ts: last.ts,
        cost_usd: Number(known.reduce((sum, entry) => sum + (entry.cost_usd ?? 0), 0).toFixed(6)),
        unknown_cost_entries: sorted.length - known.length,
        models: [...new Set(sorted.flatMap((entry) => [entry.builder.model, entry.verifier.model]))],
      };
    })
    .sort((a, b) => b.last_ts.localeCompare(a.last_ts));
}
