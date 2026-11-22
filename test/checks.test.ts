import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { runChecks } from "../src/checks.ts";
import { loadContract } from "../src/contract.ts";

const EXAMPLE = fileURLToPath(new URL("../contracts/examples/demo-greet.yaml", import.meta.url));
const DEMO_REPO = fileURLToPath(new URL("../examples/demo-repo", import.meta.url));

test("corre los checks del contrato y escribe evidencia", async () => {
  const contract = loadContract(EXAMPLE);
  const outDir = mkdtempSync(join(tmpdir(), "assistant-checks-"));
  const summary = await runChecks(contract, { repo: DEMO_REPO, attempt: 1, outDir });

  assert.equal(summary.allPassed, true);
  assert.equal(summary.results[0].passed, true);
  assert.match(summary.results[0].logPath, /01-tests\.log$/);
});

test("un check que falla marca la capa 1 como FAIL", async () => {
  const contract = loadContract(EXAMPLE);
  const failing = {
    ...contract,
    checks: [{ name: "falla", run: "node -e \"process.exit(3)\"", timeout_s: 10 }],
  };
  const outDir = mkdtempSync(join(tmpdir(), "assistant-checks-"));
  const summary = await runChecks(failing, { repo: DEMO_REPO, attempt: 1, outDir });

  assert.equal(summary.allPassed, false);
  assert.equal(summary.results[0].exitCode, 3);
});
