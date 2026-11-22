import { readFileSync } from "node:fs";
import { parse, stringify } from "yaml";

export type ProviderRef = {
  provider: string;
  model: string;
};

export type AcceptanceCriterion = {
  id: string;
  criterion: string;
  evidence: "test" | "diff" | "artifact" | "manual";
};

export type CheckSpec = {
  name: string;
  run: string;
  timeout_s?: number;
  required?: boolean;
};

export type TaskContract = {
  id: string;
  title: string;
  objective: string;
  status?: "draft" | "ready" | "running" | "blocked" | "done";
  acceptance: AcceptanceCriterion[];
  no_goals: string[];
  scope: {
    repos?: string[];
    paths_allow: string[];
    paths_deny: string[];
  };
  checks: CheckSpec[];
  models: {
    planner?: ProviderRef;
    builder: ProviderRef;
    verifier: ProviderRef;
  };
  budget: {
    max_attempts: number;
    max_minutes?: number;
    max_usd?: number;
  };
  evidence_required?: string[];
  protected_paths?: string[];
  notes?: string;
};

export class ContractError extends Error {
  readonly issues: string[];

  constructor(issues: string[]) {
    super(`Contrato inválido:\n- ${issues.join("\n- ")}`);
    this.name = "ContractError";
    this.issues = issues;
  }
}

const ID_RE = /^[a-z0-9][a-z0-9-]{1,63}$/;
const EVIDENCE = new Set(["test", "diff", "artifact", "manual"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

export function parseContract(raw: unknown): TaskContract {
  const issues: string[] = [];

  if (!isRecord(raw)) {
    throw new ContractError(["el documento debe ser un objeto YAML"]);
  }

  if (!isNonEmptyString(raw.id) || !ID_RE.test(raw.id)) {
    issues.push("id: requerido, minúsculas, números y guiones (2-64 caracteres)");
  }
  if (!isNonEmptyString(raw.title)) issues.push("title: requerido");
  if (!isNonEmptyString(raw.objective)) issues.push("objective: requerido");

  const acceptance = raw.acceptance;
  if (!Array.isArray(acceptance) || acceptance.length === 0) {
    issues.push("acceptance: al menos un criterio verificable");
  } else {
    const seen = new Set<string>();
    acceptance.forEach((item, index) => {
      if (!isRecord(item)) {
        issues.push(`acceptance[${index}]: debe ser un objeto`);
        return;
      }
      if (!isNonEmptyString(item.id)) {
        issues.push(`acceptance[${index}].id: requerido`);
      } else if (seen.has(item.id)) {
        issues.push(`acceptance[${index}].id: duplicado "${item.id}"`);
      } else {
        seen.add(item.id);
      }
      if (!isNonEmptyString(item.criterion)) {
        issues.push(`acceptance[${index}].criterion: requerido`);
      }
      if (!isNonEmptyString(item.evidence) || !EVIDENCE.has(item.evidence)) {
        issues.push(`acceptance[${index}].evidence: test | diff | artifact | manual`);
      }
    });
  }

  if (!isStringArray(raw.no_goals)) {
    issues.push("no_goals: lista de strings (puede ser vacía)");
  }

  const scope = raw.scope;
  if (!isRecord(scope)) {
    issues.push("scope: requerido");
  } else {
    if (scope.repos !== undefined && !isStringArray(scope.repos)) {
      issues.push("scope.repos: lista de strings");
    }
    if (!isStringArray(scope.paths_allow) || scope.paths_allow.length === 0) {
      issues.push("scope.paths_allow: lista no vacía de patrones permitidos");
    }
    if (!isStringArray(scope.paths_deny)) {
      issues.push("scope.paths_deny: lista de strings (puede ser vacía)");
    }
  }

  const checks = raw.checks;
  if (!Array.isArray(checks) || checks.length === 0) {
    issues.push("checks: al menos un comando determinista");
  } else {
    checks.forEach((item, index) => {
      if (!isRecord(item)) {
        issues.push(`checks[${index}]: debe ser un objeto`);
        return;
      }
      if (!isNonEmptyString(item.name)) issues.push(`checks[${index}].name: requerido`);
      if (!isNonEmptyString(item.run)) issues.push(`checks[${index}].run: requerido`);
      if (item.timeout_s !== undefined && (typeof item.timeout_s !== "number" || item.timeout_s <= 0)) {
        issues.push(`checks[${index}].timeout_s: número positivo`);
      }
      if (item.required !== undefined && typeof item.required !== "boolean") {
        issues.push(`checks[${index}].required: booleano`);
      }
    });
  }

  const models = raw.models;
  if (!isRecord(models)) {
    issues.push("models: requerido (planner, builder, verifier)");
  } else {
    for (const role of ["builder", "verifier"] as const) {
      const ref = models[role];
      if (!isRecord(ref)) {
        issues.push(`models.${role}: requerido`);
        continue;
      }
      if (!isNonEmptyString(ref.provider)) issues.push(`models.${role}.provider: requerido`);
      if (!isNonEmptyString(ref.model)) issues.push(`models.${role}.model: requerido`);
    }
    if (models.planner !== undefined) {
      const ref = models.planner;
      if (!isRecord(ref) || !isNonEmptyString(ref.provider) || !isNonEmptyString(ref.model)) {
        issues.push("models.planner: provider y model requeridos");
      }
    }
  }

  const budget = raw.budget;
  if (!isRecord(budget)) {
    issues.push("budget: requerido");
  } else {
    if (!Number.isInteger(budget.max_attempts) || (budget.max_attempts as number) < 1 || (budget.max_attempts as number) > 5) {
      issues.push("budget.max_attempts: entero entre 1 y 5");
    }
    if (budget.max_minutes !== undefined && (typeof budget.max_minutes !== "number" || budget.max_minutes <= 0)) {
      issues.push("budget.max_minutes: número positivo");
    }
    if (budget.max_usd !== undefined && (typeof budget.max_usd !== "number" || budget.max_usd <= 0)) {
      issues.push("budget.max_usd: número positivo");
    }
  }

  if (raw.evidence_required !== undefined && !isStringArray(raw.evidence_required)) {
    issues.push("evidence_required: lista de strings");
  }
  if (raw.protected_paths !== undefined && !isStringArray(raw.protected_paths)) {
    issues.push("protected_paths: lista de strings");
  }
  if (raw.status !== undefined) {
    const statuses = new Set(["draft", "ready", "running", "blocked", "done"]);
    if (!isNonEmptyString(raw.status) || !statuses.has(raw.status)) {
      issues.push("status: draft | ready | running | blocked | done");
    }
  }

  if (issues.length > 0) throw new ContractError(issues);

  const contract = raw as unknown as TaskContract;

  if (
    contract.models.builder.provider === contract.models.verifier.provider &&
    contract.models.builder.model === contract.models.verifier.model
  ) {
    throw new ContractError([
      "models.builder y models.verifier son el mismo provider y modelo; el verificador debe ser distinto",
    ]);
  }

  return contract;
}

export function loadContract(file: string): TaskContract {
  let text: string;
  try {
    text = readFileSync(file, "utf8");
  } catch (error) {
    throw new ContractError([`no se pudo leer ${file}: ${(error as Error).message}`]);
  }

  let parsed: unknown;
  try {
    parsed = parse(text);
  } catch (error) {
    throw new ContractError([`YAML inválido: ${(error as Error).message}`]);
  }

  return parseContract(parsed);
}

export function contractAsYaml(contract: TaskContract): string {
  return stringify(contract, { lineWidth: 0 });
}
