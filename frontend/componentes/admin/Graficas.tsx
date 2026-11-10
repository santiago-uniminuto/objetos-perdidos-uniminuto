"use client";

import { useState } from "react";

import type { Informe } from "@/lib/api";
import { fechaCorta, NOMBRE_SEMANA, numero } from "@/lib/formato";

import estilos from "./Graficas.module.css";

type Barra = {
  semana: string;
  valor: number;
  clase: string;
  tipo: "real" | "prediccion";
  min?: number;
  max?: number;
};

/** Pérdidas por semana: 8 semanas reales + 4 predichas con su rango del 90 %.
 *  Una sola escala; la predicción se distingue por tono, textura y leyenda (no solo por color). */
export function GraficaSemanas({ prediccion }: { prediccion: Informe["prediccion"] }) {
  const [activa, setActiva] = useState<number | null>(null);
  const barras: Barra[] = [
    ...(prediccion.historia ?? []).map((h) => ({ semana: h.semana_inicio, valor: h.perdidas, clase: h.clase, tipo: "real" as const })),
    ...prediccion.semanas.map((s) => ({
      semana: s.semana_inicio, valor: s.esperado, clase: s.clase, tipo: "prediccion" as const, min: s.minimo_90, max: s.maximo_90,
    })),
  ];
  if (barras.length === 0) return null;

  const ancho = 720;
  const alto = 260;
  const m = { arriba: 16, derecha: 8, abajo: 46, izquierda: 48 };
  const maximo = Math.max(...barras.map((b) => b.max ?? b.valor)) * 1.08;
  const paso = (ancho - m.izquierda - m.derecha) / barras.length;
  const anchoBarra = Math.min(34, paso - 8);
  const y = (v: number) => m.arriba + (alto - m.arriba - m.abajo) * (1 - v / maximo);
  const marcas = escalaBonita(maximo, 4);
  const inicioPred = barras.findIndex((b) => b.tipo === "prediccion");

  return (
    <figure className={estilos.figura}>
      <div className={estilos.leyenda} aria-hidden="true">
        <span><i className={estilos.muestraReal} /> Pérdidas reportadas</span>
        <span><i className={estilos.muestraPred} /> Predicción, con rango probable</span>
      </div>
      <div className={estilos.lienzo}>
        <svg viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label="Pérdidas por semana: reales y predichas">
          <defs>
            <pattern id="rayado" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="#5f93e8" />
              <line x1="0" y1="0" x2="0" y2="6" stroke="#ffffff" strokeWidth="1.6" opacity="0.55" />
            </pattern>
          </defs>
          {marcas.map((v) => (
            <g key={v}>
              <line x1={m.izquierda} x2={ancho - m.derecha} y1={y(v)} y2={y(v)} className={estilos.rejilla} />
              <text x={m.izquierda - 8} y={y(v) + 4} textAnchor="end" className={estilos.eje}>
                {numero(v)}
              </text>
            </g>
          ))}
          {inicioPred > 0 && (
            <line x1={m.izquierda + paso * inicioPred} x2={m.izquierda + paso * inicioPred} y1={m.arriba - 6}
              y2={alto - m.abajo} className={estilos.divisor} />
          )}
          {barras.map((b, i) => {
            const cx = m.izquierda + paso * i + paso / 2;
            const altoBarra = alto - m.abajo - y(b.valor);
            return (
              <g key={b.semana} onMouseEnter={() => setActiva(i)} onMouseLeave={() => setActiva(null)}
                onFocus={() => setActiva(i)} onBlur={() => setActiva(null)} tabIndex={0}
                aria-label={`${fechaCorta(b.semana)}: ${numero(b.valor)} ${b.tipo === "real" ? "pérdidas" : "esperadas"}`}>
                <rect x={m.izquierda + paso * i} y={m.arriba} width={paso} height={alto - m.arriba - m.abajo} fill="transparent" />
                <path d={barraRedondeada(cx - anchoBarra / 2, y(b.valor), anchoBarra, altoBarra, 4)}
                  fill={b.tipo === "real" ? "#24508f" : "url(#rayado)"} opacity={activa === null || activa === i ? 1 : 0.55} />
                {b.min !== undefined && b.max !== undefined && (
                  <g className={estilos.bigote}>
                    <line x1={cx} x2={cx} y1={y(b.max)} y2={y(b.min)} />
                    <line x1={cx - 6} x2={cx + 6} y1={y(b.max)} y2={y(b.max)} />
                    <line x1={cx - 6} x2={cx + 6} y1={y(b.min)} y2={y(b.min)} />
                  </g>
                )}
                <text x={cx} y={alto - m.abajo + 17} textAnchor="middle" className={estilos.eje}>
                  {fechaCorta(b.semana)}
                </text>
                {b.clase === "parciales" && (
                  <text x={cx} y={alto - m.abajo + 33} textAnchor="middle" className={estilos.etiquetaClase}>
                    Parciales
                  </text>
                )}
              </g>
            );
          })}
          {inicioPred > 0 && (
            <text x={m.izquierda + paso * inicioPred + 6} y={m.arriba + 4} className={estilos.eje}>
              Predicción
            </text>
          )}
        </svg>
        {activa !== null && barras[activa] && (
          <Globo barra={barras[activa]} izquierdaPct={((m.izquierda + paso * activa + paso / 2) / ancho) * 100} />
        )}
      </div>
      <details className={estilos.tabla}>
        <summary>Ver los datos en tabla</summary>
        <table>
          <thead>
            <tr><th>Semana</th><th>Tipo</th><th>Pérdidas</th><th>Rango probable</th></tr>
          </thead>
          <tbody>
            {barras.map((b) => (
              <tr key={b.semana}>
                <td>{fechaCorta(b.semana)}</td>
                <td>{NOMBRE_SEMANA[b.clase] ?? b.clase}</td>
                <td>{b.tipo === "real" ? numero(b.valor) : `${numero(b.valor)} (esperadas)`}</td>
                <td>{b.min !== undefined ? `${numero(b.min)} a ${numero(b.max)}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

function Globo({ barra, izquierdaPct }: { barra: Barra; izquierdaPct: number }) {
  return (
    <div className={estilos.globo} style={{ left: `${izquierdaPct}%` }} role="status">
      <strong>Semana del {fechaCorta(barra.semana)}</strong>
      <span>{NOMBRE_SEMANA[barra.clase] ?? barra.clase}</span>
      {barra.tipo === "real" ? (
        <span>{numero(barra.valor)} pérdidas reportadas</span>
      ) : (
        <>
          <span>{numero(Math.round(barra.valor))} esperadas</span>
          <span>Entre {numero(barra.min)} y {numero(barra.max)}</span>
        </>
      )}
    </div>
  );
}

const FRANJAS = ["06-09", "09-12", "12-15", "15-18", "18-22"];
const RAMPA = ["#eaf0f8", "#c7d6eb", "#93afd6", "#5a84bc", "#2e5c9a", "#14284a"];

/** Zona × franja horaria, rampa secuencial de un solo tono. El número va en la celda: no depende del color. */
export function MapaCalor({ celdas }: { celdas: NonNullable<Informe["metricas"]["mapa_calor"]> }) {
  const zonas = [...new Set(celdas.map((c) => c.zona))];
  const total = new Map(zonas.map((z) => [z, celdas.filter((c) => c.zona === z).reduce((a, c) => a + c.perdidas, 0)]));
  zonas.sort((a, b) => (total.get(b) ?? 0) - (total.get(a) ?? 0));
  const valor = (z: string, f: string) => celdas.find((c) => c.zona === z && c.franja === f)?.perdidas ?? 0;
  const maximo = Math.max(1, ...celdas.map((c) => c.perdidas));
  const paso = (v: number) => Math.min(RAMPA.length - 1, Math.floor((v / maximo) * RAMPA.length));

  return (
    <div className={estilos.mapa}>
      <table>
        <caption className="visualmente-oculto">Pérdidas por zona y franja horaria (histórico)</caption>
        <thead>
          <tr>
            <th scope="col">Zona</th>
            {FRANJAS.map((f) => (
              <th key={f} scope="col">{f.replace("-", " a ")} h</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {zonas.map((z) => (
            <tr key={z}>
              <th scope="row">{z}</th>
              {FRANJAS.map((f) => {
                const v = valor(z, f);
                const p = paso(v);
                return (
                  <td key={f} style={{ background: RAMPA[p], color: p >= 3 ? "#fff" : "var(--tinta)" }}>
                    {numero(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------ utilidades
function escalaBonita(maximo: number, cuantas: number): number[] {
  const crudo = maximo / cuantas;
  const potencia = 10 ** Math.floor(Math.log10(crudo));
  const paso = [1, 2, 2.5, 5, 10].map((f) => f * potencia).find((p) => p >= crudo) ?? crudo;
  const salida = [];
  for (let v = 0; v <= maximo; v += paso) salida.push(v);
  return salida;
}

/** Barra con las esquinas de arriba redondeadas (4px) y base recta sobre el eje. */
function barraRedondeada(x: number, y: number, w: number, h: number, r: number): string {
  if (h <= 0) return "";
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`;
}
