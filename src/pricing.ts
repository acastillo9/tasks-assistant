import { existsSync, readFileSync } from "node:fs";
import { parse } from "yaml";
import type { Usage } from "./verify.ts";

export type Price = {
  input_per_mtok: number;
  output_per_mtok: number;
};

export function loadPricing(file: string): Record<string, Price> {
  if (!existsSync(file)) return {};
  const parsed = parse(readFileSync(file, "utf8")) as { models?: Record<string, Price> } | null;
  return parsed?.models ?? {};
}

export function estimateCost(
  pricing: Record<string, Price>,
  model: string,
  usage: Usage,
): number | null {
  const price = pricing[model] ?? pricing[model.toLowerCase()];
  if (!price) return null;
  const input = (usage.prompt_tokens / 1_000_000) * price.input_per_mtok;
  const output = (usage.completion_tokens / 1_000_000) * price.output_per_mtok;
  return Number((input + output).toFixed(6));
}
