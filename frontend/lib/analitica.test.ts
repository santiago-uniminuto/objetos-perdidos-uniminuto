import assert from "node:assert/strict";
import { test } from "node:test";

import { pasosEmbudo, trazoChispa, zonasRadar } from "./analitica.ts";

const celdas = [
  { zona: "Aulas", franja: "09-12", perdidas: 100 },
  { zona: "Aulas", franja: "12-15", perdidas: 20 },
  { zona: "Biblioteca", franja: "12-15", perdidas: 60 },
  { zona: "Cafetería", franja: "12-15", perdidas: 10 },
  { zona: "Cafetería", franja: "sin hora", perdidas: 999 },
];

test("zonasRadar: la zona con más pérdidas queda al centro y como crítica", () => {
  const z = zonasRadar(celdas, null);
  const aulas = z.find((x) => x.zona === "Aulas")!;
  const cafe = z.find((x) => x.zona === "Cafetería")!;
  assert.equal(aulas.total, 120);
  assert.equal(cafe.total, 10); // "sin hora" no cuenta en el radar
  assert.equal(aulas.nivel, "Crítico");
  const dist = (p: { x: number; y: number }) => Math.hypot(p.x - 50, p.y - 50);
  assert.ok(dist(aulas) < dist(cafe));
});

test("zonasRadar: al elegir franja cambia el valor pero no el ángulo", () => {
  const dia = zonasRadar(celdas, null);
  const mediodia = zonasRadar(celdas, "12-15");
  const bib = mediodia.find((x) => x.zona === "Biblioteca")!;
  assert.equal(bib.valor, 60);
  assert.equal(bib.nivel, "Crítico");
  const ang = (p: { x: number; y: number }) => Math.atan2(p.y - 50, p.x - 50).toFixed(4);
  assert.deepEqual(dia.map(ang), mediodia.map(ang));
});

test("zonasRadar: limita la cantidad de zonas a las de más pérdidas", () => {
  assert.deepEqual(zonasRadar(celdas, null, 2).map((z) => z.zona), ["Aulas", "Biblioteca"]);
});

test("pasosEmbudo y trazoChispa", () => {
  const p = pasosEmbudo({ reportados: 400, con_sugerencia: 320, verificados: 230, entregados: 200 });
  assert.deepEqual(p.map((x) => x.pct), [100, 80, 58, 50]);
  assert.equal(trazoChispa([1], 100, 30), "");
  assert.ok(trazoChispa([1, 2, 3], 100, 30).startsWith("M0.0 27.0"));
});
