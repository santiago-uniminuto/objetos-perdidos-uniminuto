import assert from "node:assert/strict";
import { test } from "node:test";

import { ErrorApi } from "./api.ts";
import { leerExplicacion } from "./explicacion.ts";
import { erroresPorCampo, traducir } from "./validacion.ts";

test("explicación del matcher separada en partes", () => {
  const e = leerExplicacion("[alta] Ambos son termos azules con sticker. Coincide en: color, tipo, sticker. Difiere en: marca.");
  assert.deepEqual(e, { confianza: "alta", texto: "Ambos son termos azules con sticker.", coincide: ["color", "tipo", "sticker"], difiere: ["marca"] });
  assert.deepEqual(leerExplicacion("Parecidos por el color."), { confianza: null, texto: "Parecidos por el color.", coincide: [], difiere: [] });
  assert.equal(leerExplicacion(null), null);
});

test("errores de validación de la API en español y por campo", () => {
  assert.equal(traducir("String should have at least 5 characters"), "Escribe al menos 5 caracteres.");
  assert.equal(traducir("value is not a valid email address: An email address must have an @-sign."),
    "Escribe un correo válido, por ejemplo nombre@uniminuto.edu.co.");
  const e = new ErrorApi(422, "validacion", "Datos inválidos", [
    { campo: "telefono", error: "String should match pattern '^\\+?[0-9 ]{7,15}$'" },
    { campo: "nombres", error: "Field required" },
  ]);
  assert.deepEqual(erroresPorCampo(e), { telefono: "El formato no es válido.", nombres: "Este campo es obligatorio." });
  assert.deepEqual(erroresPorCampo(new ErrorApi(409, "conflicto", "x")), {});
});
