import assert from "node:assert/strict";
import { test } from "node:test";
import { fechaCorta, fechaLarga, haceCuanto, mesDePeriodo, numero } from "./formato.ts";

test("números en formato colombiano", () => {
  assert.equal(numero(5118), "5.118");
  assert.equal(numero(50.7, 1), "50,7");
  assert.equal(numero(null), "sin dato");
});

test("fechas sin corrimiento de zona horaria", () => {
  assert.equal(fechaLarga("2026-11-09"), "9 de noviembre de 2026");
  assert.equal(fechaCorta("2026-11-09T05:00:00Z"), "9 nov");
  assert.equal(mesDePeriodo("2026-10"), "octubre de 2026");
});

test("hace cuánto", () => {
  const hoy = new Date(2026, 10, 10);
  assert.equal(haceCuanto("2026-11-10", hoy), "hoy");
  assert.equal(haceCuanto("2026-11-09", hoy), "ayer");
  assert.equal(haceCuanto("2026-11-03", hoy), "hace 7 días");
  assert.equal(haceCuanto("2026-09-01", hoy), "1 de septiembre de 2026");
});
