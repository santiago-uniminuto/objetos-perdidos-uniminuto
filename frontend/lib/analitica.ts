// Lógica pura del tablero de analítica (sin React): se prueba en analitica.test.ts.

export const FRANJAS = ["06-09", "09-12", "12-15", "15-18", "18-22"] as const;
export type Franja = (typeof FRANJAS)[number];

export type Celda = { zona: string; franja: string; perdidas: number };

export type ZonaRadar = {
  zona: string;
  /** Pérdidas por franja, en el orden de FRANJAS */
  porFranja: number[];
  total: number;
  /** Valor para la franja elegida (o el día completo) */
  valor: number;
  /** valor / máximo de las zonas visibles, entre 0 y 1 */
  peso: number;
  nivel: "Crítico" | "Alto" | "Medio" | "Bajo";
  /** Posición en el radar, en % del lado (0 a 100). Más cerca del centro = más pérdidas. */
  x: number;
  y: number;
};

export function nivelDe(peso: number): ZonaRadar["nivel"] {
  if (peso > 0.66) return "Crítico";
  if (peso > 0.4) return "Alto";
  if (peso > 0.2) return "Medio";
  return "Bajo";
}

/** Zonas del radar: las `cuantas` con más pérdidas en el día. El ángulo de cada zona es fijo (orden
 *  alfabético) para que al cambiar de franja solo se acerquen o alejen del centro, sin saltar de lugar. */
export function zonasRadar(celdas: Celda[], franja: Franja | null, cuantas = 8): ZonaRadar[] {
  const porZona = new Map<string, number[]>();
  for (const c of celdas) {
    const i = FRANJAS.indexOf(c.franja as Franja);
    if (i < 0) continue;
    const fila = porZona.get(c.zona) ?? [0, 0, 0, 0, 0];
    fila[i] = (fila[i] ?? 0) + c.perdidas;
    porZona.set(c.zona, fila);
  }
  const todas = [...porZona].map(([zona, porFranja]) => ({ zona, porFranja, total: porFranja.reduce((a, b) => a + b, 0) }));
  const visibles = todas.sort((a, b) => b.total - a.total).slice(0, cuantas).sort((a, b) => a.zona.localeCompare(b.zona, "es"));
  const fi = franja === null ? -1 : FRANJAS.indexOf(franja);
  const valores = visibles.map((z) => (fi < 0 ? z.total : (z.porFranja[fi] ?? 0)));
  const maximo = Math.max(1, ...valores);
  return visibles.map((z, i) => {
    const valor = valores[i] ?? 0;
    const peso = valor / maximo;
    const angulo = (-90 + (360 / visibles.length) * i) * (Math.PI / 180);
    const radio = 11 + (1 - peso) * 34; // entre 11 % (crítico) y 45 % (casi nada) del lado
    return { ...z, valor, peso, nivel: nivelDe(peso), x: 50 + radio * Math.cos(angulo), y: 50 + radio * Math.sin(angulo) };
  });
}

/** Del reporte a la entrega: cada paso con su porcentaje sobre los reportados. */
export function pasosEmbudo(e: { reportados: number; con_sugerencia: number; verificados: number; entregados: number }) {
  const base = Math.max(1, e.reportados);
  return [
    { nombre: "Reportados", valor: e.reportados },
    { nombre: "Con sugerencia de la IA", valor: e.con_sugerencia },
    { nombre: "Verificados por el admin", valor: e.verificados },
    { nombre: "Entregados al dueño", valor: e.entregados },
  ].map((p) => ({ ...p, pct: Math.round((100 * p.valor) / base) }));
}

/** Trazo de una línea pequeña (sparkline) en un lienzo de ancho × alto. */
export function trazoChispa(valores: number[], ancho: number, alto: number): string {
  if (valores.length < 2) return "";
  const min = Math.min(...valores), max = Math.max(...valores);
  const rango = max - min || 1;
  return valores
    .map((v, i) => `${i ? "L" : "M"}${((i / (valores.length - 1)) * ancho).toFixed(1)} ${(alto - 3 - ((v - min) / rango) * (alto - 6)).toFixed(1)}`)
    .join(" ");
}
