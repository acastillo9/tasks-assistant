import assert from "node:assert/strict";
import { test } from "node:test";
import { greet } from "../src/greet.js";

test("saluda por nombre", () => {
  assert.equal(greet("Andrés"), "Hola, Andrés!");
});

test("no acepta nombres vacíos", () => {
  assert.throws(() => greet(""), /nombre requerido/);
});
