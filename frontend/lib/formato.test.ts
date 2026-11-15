import assert from "node:assert/strict";
import { test } from "node:test";
import { cuentaRegresiva, fechaCorta, fechaLarga, haceCuanto, mesDePeriodo, numero } from "./formato.ts";

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

test("cuenta regresiva hasta la próxima corrida del analista", () => {
  const base = Date.parse("2026-11-14T12:00:00Z");
  assert.equal(cuentaRegresiva("2026-11-14T14:05:09Z", base), "2 h 05 min 09 s");
  assert.equal(cuentaRegresiva("2026-11-14T12:03:07Z", base), "3 min 07 s");
  assert.equal(cuentaRegresiva("2026-11-14T12:00:42Z", base), "42 s");
  assert.equal(cuentaRegresiva("2026-11-14T11:59:00Z", base), null);
});
