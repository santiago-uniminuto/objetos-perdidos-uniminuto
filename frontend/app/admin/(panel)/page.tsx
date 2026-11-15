"use client";

import { useEffect, useState } from "react";

import { GraficaSemanas, MapaCalor } from "@/componentes/admin/Graficas";
import { useUsuario } from "@/componentes/admin/Sesion";
import { api, type Catalogos, ErrorApi, type Informe, sedesPorRegion } from "@/lib/api";
import { fechaLarga, mesDePeriodo, numero } from "@/lib/formato";

import estilos from "./tablero.module.css";

export default function Tablero() {
  const usuario = useUsuario();
  // "global" o el id de una sede. Admin y auditor ven cualquier sede (solo agregados, ADR-019).
  const [alcance, setAlcance] = useState<string>(usuario.rol === "auditor" || usuario.sede_id == null ? "global" : String(usuario.sede_id));
  const [sedes, setSedes] = useState<Catalogos["sedes"]>([]);
  const [informe, setInforme] = useState<Informe | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          <section className={estilos.resumen} aria-labelledby="resumen-titulo">
            <h2 id="resumen-titulo" className="visualmente-oculto">Resumen</h2>
            <p className={estilos.texto}>{informe.resumen}</p>
            <p className={estilos.fuente}>
              {informe.resumen_fuente === "llm"
                ? `Redactado por IA (${informe.modelo_llm}) y verificado: cada cifra se comprobó contra los datos.`
                : "Texto automático: la redacción de la IA no pasó la verificación de cifras, así que se usó la plantilla."}
            </p>
          </section>

          {m.mes?.periodo && (
            <section className={estilos.indicadores} aria-label={`Indicadores de ${mesDePeriodo(m.mes.periodo)}`}>
              <Indicador nombre={`Recuperado en ${mesDePeriodo(m.mes.periodo)}`} valor={`${numero(m.mes.tasa_recuperacion_pct, 1)} %`}
                nota={m.mes.tasa_mes_anterior_pct !== null ? `Mes anterior: ${numero(m.mes.tasa_mes_anterior_pct, 1)} %` : undefined} />
              <Indicador nombre="Objetos reportados" valor={numero(m.mes.reportados)} nota={`${numero(m.mes.recuperados)} devueltos a su dueño`} />
              <Indicador nombre="Días hasta devolverlo" valor={numero(m.mes.dias_tipicos_hasta_recuperar, 1)} nota="Valor típico del mes" />
              {m.matching_4_semanas && (
                <Indicador nombre="Sugerencias de la IA correctas" valor={`${numero(m.matching_4_semanas.precision_pct, 1)} %`}
                  nota={`De las revisadas en 4 semanas (${numero(m.matching_4_semanas.sugeridas)} sugeridas)`} />
              )}
            </section>
          )}

          <section className={estilos.bloque} aria-labelledby="semanas-titulo">
            <h2 id="semanas-titulo">Pérdidas por semana</h2>
            {p.semanas?.length ? <GraficaSemanas prediccion={p} /> : <p className="secundario">Aún no hay semanas suficientes para graficar.</p>}
            {p.backtest && (
              <p className="secundario pequeno">
                {p.backtest.gana_modelo
                  ? `En las últimas ${p.backtest.semanas_evaluadas} semanas la predicción se equivocó en promedio ${numero(p.backtest.mae_modelo, 1)} objetos por semana; una estimación simple (promedio de 4 semanas) se equivocó ${numero(p.backtest.mae_ingenuo, 1)}.`
                  : "La predicción no supera a una estimación simple: tómala con cautela."}
              </p>
            )}
          </section>

          {(m.mapa_calor?.length ?? 0) > 0 && (
            <section className={estilos.bloque} aria-labelledby="mapa-titulo">
              <h2 id="mapa-titulo">Dónde y a qué hora se pierden las cosas</h2>
              <p className="secundario pequeno">Pérdidas reportadas desde el inicio, por zona y franja horaria.</p>
              <MapaCalor celdas={m.mapa_calor!} />
            </section>
          )}

          <p className="secundario pequeno">
            Datos hasta el {fechaLarga(informe.datos_hasta)}. El agente analista actualiza este informe cada pocas horas.
          </p>
        </>
      )}
    </div>
  );
}

function Indicador({ nombre, valor, nota }: { nombre: string; valor: string; nota?: string }) {
  return (
    <div className={estilos.indicador}>
      <p className={estilos.nombre}>{nombre}</p>
      <p className={estilos.valor}>{valor}</p>
      {nota && <p className="secundario pequeno">{nota}</p>}
    </div>
  );
}
