"use client";

import { useEffect, useState } from "react";

import {
  Categorias, CifrasPrediccion, Embudo, FiltroFranja, Indicadores, InformeCompleto, RadarZonas, ResumenAgente, Seccion,
} from "@/componentes/admin/Analitica";
import estilosA from "@/componentes/admin/Analitica.module.css";
import { GraficaSemanas, MapaCalor } from "@/componentes/admin/Graficas";
import { useUsuario } from "@/componentes/admin/Sesion";
import type { Franja } from "@/lib/analitica";
import { api, type Catalogos, ErrorApi, type Informe, sedesPorRegion } from "@/lib/api";
import { cuentaRegresiva, fechaLarga, haceCuanto, numero, rangoSemana } from "@/lib/formato";

import estilos from "./tablero.module.css";

export default function Tablero() {
  const usuario = useUsuario();
  // "global" o el id de una sede. Admin y auditor ven cualquier sede (solo agregados, ADR-019).
  const [alcance, setAlcance] = useState<string>(usuario.rol === "auditor" || usuario.sede_id == null ? "global" : String(usuario.sede_id));
  const [sedes, setSedes] = useState<Catalogos["sedes"]>([]);
  const [informe, setInforme] = useState<Informe | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [franja, setFranja] = useState<Franja | null>(null);
  const [verInforme, setVerInforme] = useState(false);

  useEffect(() => {
    api<Catalogos>("/catalogos").then((c) => setSedes(c.sedes)).catch(() => undefined);
  }, []);

  useEffect(() => {
    setError(null);
    const q = alcance === "global" ? "alcance=global" : `sede_id=${alcance}`;
    api<Informe>(`/analitica/resumen?${q}`)
      .then(setInforme)
      .catch((e) => {
        setInforme(null);
        setError(e instanceof ErrorApi ? e.message : "No se pudo cargar la analítica.");
      });
  }, [alcance, usuario.rol]);

  const m = informe?.metricas;
  const p = informe?.prediccion;

  return (
    <div className={estilos.tablero}>
      <header className={estilos.cabecera}>
        <div>
          <h1 className={estilos.titulo}>Analítica</h1>
          {m && <p className="secundario">{m.sede}</p>}
        </div>
        <label className="campo">
          <span>Ver</span>
          <select value={alcance} onChange={(e) => setAlcance(e.target.value)}>
            <option value="global">Todas las sedes</option>
            {sedes.length === 0 && usuario.sede_id != null && <option value={String(usuario.sede_id)}>Mi sede</option>}
            {sedesPorRegion(sedes).map(([region, lista]) => (
              <optgroup key={region} label={region}>
                {lista.map((s) => (
                  <option key={s.id} value={String(s.id)}>
                    {s.nombre}{s.id === usuario.sede_id ? " (mi sede)" : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
      </header>

      {error && <p className="aviso aviso-error" role="alert">{error}</p>}

      {informe && m && p && (
        <>
          <ProximaCorrida informe={informe} />
          <ResumenAgente informe={informe} onAbrir={() => setVerInforme(true)} />
          <InformeCompleto informe={informe} abierto={verInforme} onCerrar={() => setVerInforme(false)} />

          {m.mes?.periodo && (
            <Seccion n={1} titulo="¿Cuánto recuperamos?" sub="Lo que pasó el último mes completo frente al anterior">
              <Indicadores m={m} />
            </Seccion>
          )}

          {(m.mapa_calor?.length ?? 0) > 0 && (
            <Seccion n={2} titulo="¿Dónde y cuándo se pierde?" sub="Para decidir dónde y a qué hora reforzar las rondas (histórico de pérdidas)"
              derecha={<FiltroFranja franja={franja} onCambiar={setFranja} />}>
              <RadarZonas celdas={m.mapa_calor!} franja={franja} />
              <details className={estilos.tablaDatos}>
                <summary>Ver todas las zonas en tabla (zona × franja horaria)</summary>
                <MapaCalor celdas={m.mapa_calor!} />
              </details>
            </Seccion>
          )}

          <Seccion n={3} titulo="¿Qué se recupera y qué viene?" sub="Recuperación por tipo de objeto y predicción de las próximas semanas">
            <div className={estilosA.dosColumnas}>
              <Categorias m={m} />
              <div className={`${estilosA.vidrio} ${estilosA.tarjeta}`}>
                <div>
                  <h3>Predicción semanal</h3>
                  {p.semanas[0] && (
                    <p className="secundario pequeno">
                      Semana del {rangoSemana(p.semanas[0].semana_inicio)}: {numero(Math.round(p.semanas[0].esperado))} pérdidas
                      (rango {numero(p.semanas[0].minimo_90)} a {numero(p.semanas[0].maximo_90)})
                    </p>
                  )}
                </div>
                {p.semanas?.length ? <GraficaSemanas prediccion={p} /> : <p className="secundario">Aún no hay semanas suficientes para graficar.</p>}
                <CifrasPrediccion p={p} />
                {p.backtest && !p.backtest.gana_modelo && (
                  <p className="secundario pequeno">La predicción no supera a una estimación simple: tómala con cautela.</p>
                )}
              </div>
            </div>
          </Seccion>

          <Seccion n={4} titulo="¿La IA ayuda?" sub="Del reporte a la entrega, con la IA en el medio">
            <Embudo m={m} />
          </Seccion>

          <p className="secundario pequeno">
            Datos hasta el {fechaLarga(informe.datos_hasta)}. El agente analista actualiza este informe cada{" "}
            {informe.cada_horas === 1 ? "hora" : `${numero(informe.cada_horas)} horas`}.
          </p>
        </>
      )}
    </div>
  );
}

/** Contador hasta la próxima corrida del agente analista (misma regla que su programador). */
function ProximaCorrida({ informe }: { informe: Informe }) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setAhora(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  if (!informe.proxima_corrida) return null;
  const falta = cuentaRegresiva(informe.proxima_corrida, ahora);
  return (
    <p className={estilos.reloj}>
      <span className={estilos.relojEtiqueta}>Próxima actualización del agente</span>
      {falta ? (
        <span className={estilos.relojValor} aria-label={`en ${falta}`}>{falta}</span>
      ) : (
        <span className={estilos.relojValor}>en curso: recarga en unos minutos</span>
      )}
      {informe.ultima_corrida && <span className="secundario pequeno">Última: {haceCuanto(informe.ultima_corrida)}</span>}
    </p>
  );
}
