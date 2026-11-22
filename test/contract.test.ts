import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { ContractError, loadContract, parseContract } from "../src/contract.ts";

const EXAMPLE = fileURLToPath(new URL("../contracts/examples/demo-greet.yaml", import.meta.url));

test("carga el contrato de ejemplo", () => {
  const contract = loadContract(EXAMPLE);
  assert.equal(contract.id, "demo-greet");
  assert.equal(contract.acceptance.length, 2);
  assert.equal(contract.checks[0].run, "npm test");
});

test("rechaza ids de aceptación duplicados", () => {
  const raw = {
    id: "tarea-1",
    title: "T",
    objective: "O",
    acceptance: [
      { id: "A1", criterion: "c", evidence: "test" },
      { id: "A1", criterion: "d", evidence: "test" },
    ],
    no_goals: [],
    scope: { paths_allow: ["src/**"], paths_deny: [] },
    checks: [{ name: "tests", run: "npm test" }],
    models: {
      builder: { provider: "deepseek", model: "deepseek-chat" },
      verifier: { provider: "openrouter", model: "anthropic/claude-sonnet-4.5" },
    },
    budget: { max_attempts: 2 },
  };

  assert.throws(() => parseContract(raw), (error) => {
    assert.ok(error instanceof ContractError);
    assert.match(error.message, /duplicado "A1"/);
    return true;
  });
});

test("rechaza builder y verifier idénticos", () => {
  const raw = {
    id: "tarea-2",
    title: "T",
    objective: "O",
    acceptance: [{ id: "A1", criterion: "c", evidence: "test" }],
    no_goals: [],
    scope: { paths_allow: ["src/**"], paths_deny: [] },
    checks: [{ name: "tests", run: "npm test" }],
    models: {
      builder: { provider: "deepseek", model: "deepseek-chat" },
      verifier: { provider: "deepseek", model: "deepseek-chat" },
    },
    budget: { max_attempts: 2 },
  };

  assert.throws(() => parseContract(raw), /mismo provider y modelo/);
});

test("exige comandos de test", () => {
  const raw = {
    id: "tarea-3",
    title: "T",
    objective: "O",
    acceptance: [{ id: "A1", criterion: "c", evidence: "test" }],
    no_goals: [],
    scope: { paths_allow: ["src/**"], paths_deny: [] },
    checks: [],
    models: {
      builder: { provider: "a", model: "b" },
      verifier: { provider: "c", model: "d" },
    },
    budget: { max_attempts: 2 },
  };

  assert.throws(() => parseContract(raw), /al menos un comando determinista/);
});
