import assert from "node:assert/strict";
import { test } from "node:test";

import { revisarDescripcion } from "./descripcion.ts";

test("descripción completa: qué es, marca, color y un detalle", () => {
  const r = revisarDescripcion("Celular iPhone 13 Pro Max azul, con forro transparente y la pantalla rota");
  assert.deepEqual([r.que, r.marca, r.color, r.detalle], [true, true, true, true]);
});

test("'modelo: promax color: azul' no dice qué objeto es ni la marca", () => {
  const r = revisarDescripcion("modelo: promax color:azul");
  assert.deepEqual([r.que, r.marca, r.color, r.detalle, r.campos], [false, false, true, true, true]);
});

test("por campos también sirve", () => {
  const r = revisarDescripcion("tipo: billetera, marca: Tous, color: rosada, señas: llavero de oso");
  assert.deepEqual([r.que, r.marca, r.color, r.detalle], [true, true, true, true]);
});
