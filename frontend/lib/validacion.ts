// Traduce los errores 422 de la API (Pydantic, en inglés) a mensajes por campo en español.

import { ErrorApi } from "./api.ts";

const TRADUCCIONES: [RegExp, string][] = [
  [/institucional/i, "Usa tu correo institucional (@uniminuto.edu o @uniminuto.edu.co)."],
  [/valid email/i, "Escribe un correo válido, por ejemplo nombre@uniminuto.edu.co."],
  [/match pattern/i, "El formato no es válido."],
  [/at least (\d+) character/i, "Escribe al menos $1 caracteres."],
  [/at most (\d+) character/i, "Máximo $1 caracteres."],
  [/field required|missing/i, "Este campo es obligatorio."],
  [/valid date/i, "Escribe una fecha válida."],
  [/futuro/i, "La fecha no puede estar en el futuro."],
  [/valid UUID/i, "Identificador inválido: vuelve a seleccionar el registro."],
];

export function traducir(error: string): string {
  for (const [patron, texto] of TRADUCCIONES) {
    const m = patron.exec(error);
    if (m) return texto.replace("$1", m[1] ?? "");
  }
  return error;
}

/** { campo: mensaje } a partir de un ErrorApi 422; vacío si no es un error de validación. */
export function erroresPorCampo(e: unknown): Record<string, string> {
  if (!(e instanceof ErrorApi) || e.estado !== 422 || !Array.isArray(e.detalle)) return {};
  const salida: Record<string, string> = {};
  for (const d of e.detalle as { campo?: string; error?: string }[]) {
    if (d.campo && d.error && !salida[d.campo]) salida[d.campo] = traducir(d.error);
  }
  return salida;
}
