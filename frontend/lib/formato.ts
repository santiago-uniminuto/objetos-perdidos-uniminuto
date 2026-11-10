// Formatos en español de Colombia (1.234 y 50,7).

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
  "noviembre", "diciembre"];
const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

export function numero(n: number | null | undefined, decimales = 0): string {
  if (n === null || n === undefined) return "sin dato";
  return n.toLocaleString("es-CO", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

/** "2026-11-09" -> fecha local sin corrimiento de zona horaria. */
function partes(iso: string): [number, number, number] {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return [a ?? 1970, m ?? 1, d ?? 1];
}

export function fechaLarga(iso: string): string {
  const [a, m, d] = partes(iso);
  return `${d} de ${MESES[m - 1]} de ${a}`;
}

export function fechaCorta(iso: string): string {
  const [, m, d] = partes(iso);
  return `${d} ${MESES_CORTOS[m - 1]}`;
}

export function mesDePeriodo(periodo: string): string {
  const [a, m] = periodo.split("-").map(Number);
  return `${MESES[(m ?? 1) - 1]} de ${a}`;
}

/** Hace cuánto, en palabras: "hoy", "ayer", "hace 5 días", o la fecha. */
export function haceCuanto(iso: string, hoy: Date = new Date()): string {
  const [a, m, d] = partes(iso);
  const dias = Math.round((Date.UTC(hoy.getFullYear(), hoy.getMonth(), hoy.getDate()) - Date.UTC(a, m - 1, d)) / 86400000);
  if (dias <= 0) return "hoy";
  if (dias === 1) return "ayer";
  if (dias < 30) return `hace ${dias} días`;
  return fechaLarga(iso);
}

export const NOMBRE_SEMANA: Record<string, string> = {
  parciales: "Parciales",
  vacaciones: "Vacaciones",
  inicio: "Inicio de semestre",
  normal: "Semana normal",
};
