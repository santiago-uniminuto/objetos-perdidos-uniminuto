"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { type Celda, FRANJAS, type Franja, pasosEmbudo, trazoChispa, zonasRadar } from "@/lib/analitica";
import type { Informe } from "@/lib/api";
import { fechaCorta, mesDePeriodo, numero, rangoSemana } from "@/lib/formato";

import estilos from "./Analitica.module.css";

function claseNivel(nivel: string): string {
  return { "Crítico": estilos.critico, Alto: estilos.alto, Medio: estilos.medio, Bajo: estilos.bajo }[nivel] ?? "";
}

const NOMBRE_FRANJA = (f: string) => `${f.replace("-", "–")} h`;

// ------------------------------------------------------------------ encabezado de sección numerada
export function Seccion({ n, titulo, sub, derecha, children }: {
  n: number; titulo: string; sub: string; derecha?: React.ReactNode; children: React.ReactNode;
}) {
  const id = `seccion-${n}`;
  return (
    <section className={estilos.seccion} aria-labelledby={id}>
      <div className={estilos.seccionCabeza}>
        <div className={estilos.seccionTitulo}>
          <span className={estilos.numeroSeccion} aria-hidden="true">{n}</span>
          <div>
            <h2 id={id}>{titulo}</h2>
            <p className="secundario">{sub}</p>
          </div>
        </div>
        {derecha}
      </div>
      {children}
    </section>
  );
}

// ------------------------------------------------------------------ resumen del agente
export function ResumenAgente({ informe, onAbrir }: { informe: Informe; onAbrir: () => void }) {
  const m = informe.metricas, p = informe.prediccion;
  const semana = p.semanas[0];
  const critica = m.zonas_criticas?.[0];
  return (
    <section className={estilos.hero} aria-labelledby="hero-titulo">
      <div className={estilos.heroFila}>
        <span className={estilos.chipIa}>
          Resumen del agente analista · {informe.resumen_fuente === "llm" ? "✓ cifras verificadas" : "texto automático"}
        </span>
        {semana && <span className={estilos.fechaSemana}>{rangoSemana(semana.semana_inicio)}</span>}
      </div>
      {semana ? (
        <p id="hero-titulo" className={estilos.heroTitulo}>
          Esta semana se esperan <span className={estilos.resalta}>{numero(Math.round(semana.esperado))} pérdidas</span>{" "}
          {m.sede === "Todas las sedes" ? "en todas las sedes" : "en la sede"}
        </p>
      ) : (
        <p id="hero-titulo" className={estilos.heroTitulo}>{m.sede}</p>
      )}
      <p className={estilos.heroTexto}>{informe.resumen}</p>
      <div className={estilos.hallazgos}>
        {critica && (
          <Hallazgo n={1} tono="senal" titulo={`${critica.zona}, ${critica.dia} de ${NOMBRE_FRANJA(critica.franja)}`}
            texto={`${numero(critica.perdidas)} pérdidas en el histórico${m.zonas_criticas!.length > 1
              ? ` (${m.zonas_criticas!.slice(1).map((z) => `${z.dia} ${numero(z.perdidas)}`).join(" · ")})` : ""}`} />
        )}
        {p.backtest && (
          <Hallazgo n={2} tono="azul" titulo={p.backtest.gana_modelo ? "Predicción confiable" : "Predicción con cautela"}
            texto={`Error de ${numero(p.backtest.mae_modelo, 1)} por semana frente a ${numero(p.backtest.mae_ingenuo, 1)} de una estimación simple`} />
        )}
        {m.matching_4_semanas && (
          <Hallazgo n={3} tono="verde" titulo="La IA acierta"
            texto={`${numero(m.matching_4_semanas.precision_pct, 1)} % de las sugerencias revisadas eran el objeto correcto`} />
        )}
      </div>
      <div className={estilos.heroPie}>
        <p className="secundario pequeno">
          {m.sede} · {informe.resumen_fuente === "llm" ? `redactado por IA (${informe.modelo_llm}) y verificado` : "plantilla automática"}
        </p>
        <button type="button" className={estilos.botonSenal} onClick={onAbrir}>
          Leer informe completo <span aria-hidden="true">→</span>
        </button>
      </div>
    </section>
  );
}

function Hallazgo({ n, tono, titulo, texto }: { n: number; tono: "senal" | "azul" | "verde"; titulo: string; texto: string }) {
  return (
    <div className={estilos.hallazgo}>
      <span className={`${estilos.insignia} ${estilos[tono]}`} aria-hidden="true">{n}</span>
      <div>
        <p className={estilos.hallazgoTitulo}>{titulo}</p>
        <p className="secundario pequeno">{texto}</p>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ indicadores con tendencia
export function Indicadores({ m }: { m: Informe["metricas"] }) {
  const mes = m.mes!;
  const t = m.tendencia_meses ?? [];
  const cambio = mes.tasa_mes_anterior_pct !== null ? mes.tasa_recuperacion_pct - mes.tasa_mes_anterior_pct : null;
  const dias = t.map((x) => x.dias_tipicos_hasta_recuperar).filter((x): x is number => x !== null);
  const cambioDias = dias.length > 1 ? dias[dias.length - 1]! - dias[dias.length - 2]! : null;
  return (
    <div className={estilos.kpis}>
      <Kpi nombre={`Recuperado en ${mesDePeriodo(mes.periodo).split(" ")[0]}`} valor={`${numero(mes.tasa_recuperacion_pct, 1)} %`}
        insignia={cambio !== null ? `${cambio >= 0 ? "▲" : "▼"} ${numero(Math.abs(cambio), 1)} pts` : undefined} buena={cambio !== null && cambio >= 0}
        nota={mes.tasa_mes_anterior_pct !== null ? `Mes anterior: ${numero(mes.tasa_mes_anterior_pct, 1)} %` : undefined}
        serie={t.map((x) => x.tasa_recuperacion_pct)} />
      <Kpi nombre="Objetos reportados" valor={numero(mes.reportados)} insignia={`${numero(mes.recuperados)} devueltos`}
        nota={mesDePeriodo(mes.periodo)} serie={t.map((x) => x.reportados)} />
      <Kpi nombre="Días hasta devolverlo" valor={numero(mes.dias_tipicos_hasta_recuperar, 1)}
        insignia={cambioDias !== null ? `${cambioDias <= 0 ? "▼" : "▲"} ${numero(Math.abs(cambioDias), 1)} días` : undefined}
        buena={cambioDias !== null && cambioDias <= 0} nota="Valor típico del mes" serie={dias} />
      {m.matching_4_semanas && (
        <Kpi nombre="Aciertos de la IA" valor={`${numero(m.matching_4_semanas.precision_pct, 1)} %`}
          insignia={`${numero(m.matching_4_semanas.sugeridas)} sugeridas`} nota="Revisadas en 4 semanas" anillo={m.matching_4_semanas.precision_pct} />
      )}
    </div>
  );
}

function Kpi({ nombre, valor, insignia, buena, nota, serie, anillo }: {
  nombre: string; valor: string; insignia?: string; buena?: boolean; nota?: string; serie?: number[]; anillo?: number;
}) {
  const trazo = serie ? trazoChispa(serie, 120, 36) : "";
  return (
    <div className={estilos.kpi}>
      <div className={estilos.kpiCabeza}>
        <p className={estilos.kpiNombre}>{nombre}</p>
        {insignia && <span className={`${estilos.pastilla} ${buena ? estilos.pastillaBuena : ""}`}>{insignia}</span>}
      </div>
      <div className={estilos.kpiCuerpo}>
        <p className={estilos.kpiValor}>{valor}</p>
        {trazo && (
          <svg viewBox="0 0 120 36" className={estilos.chispa} aria-hidden="true">
            <path d={trazo} />
          </svg>
        )}
        {anillo !== undefined && <Anillo pct={anillo} tam={56} grosor={7} />}
      </div>
      {nota && <p className="secundario pequeno">{nota}</p>}
    </div>
  );
}

function Anillo({ pct, tam, grosor, children }: { pct: number; tam: number; grosor: number; children?: React.ReactNode }) {
  const r = (tam - grosor) / 2, c = 2 * Math.PI * r;
  return (
    <div className={estilos.anillo} style={{ width: tam, height: tam }}>
      <svg viewBox={`0 0 ${tam} ${tam}`} aria-hidden="true">
        <circle cx={tam / 2} cy={tam / 2} r={r} className={estilos.anilloFondo} strokeWidth={grosor} />
        <circle cx={tam / 2} cy={tam / 2} r={r} className={estilos.anilloValor} strokeWidth={grosor}
          strokeDasharray={`${(c * Math.min(100, pct)) / 100} ${c}`} transform={`rotate(-90 ${tam / 2} ${tam / 2})`} />
      </svg>
      {children && <div className={estilos.anilloCentro}>{children}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ radar de zonas
export function FiltroFranja({ franja, onCambiar }: { franja: Franja | null; onCambiar: (f: Franja | null) => void }) {
  const opciones: (Franja | null)[] = [null, ...FRANJAS];
  return (
    <div className={estilos.franjas} role="group" aria-label="Franja horaria">
      {opciones.map((f) => (
        <button key={f ?? "dia"} type="button" aria-pressed={franja === f} onClick={() => onCambiar(f)}
          className={`${estilos.franja} ${franja === f ? estilos.franjaActiva : ""}`}>
          {f === null ? "Todo el día" : NOMBRE_FRANJA(f)}
        </button>
      ))}
    </div>
  );
}

export function RadarZonas({ celdas, franja }: { celdas: Celda[]; franja: Franja | null }) {
  const zonas = useMemo(() => zonasRadar(celdas, franja), [celdas, franja]);
  const [elegida, setElegida] = useState<string | null>(null);
  const actual = zonas.find((z) => z.zona === elegida) ?? [...zonas].sort((a, b) => b.total - a.total)[0];
  const textoFranja = franja === null ? "todo el día" : NOMBRE_FRANJA(franja);
  const ranking = [...zonas].sort((a, b) => b.valor - a.valor);
  if (!actual) return null;

  const pico = Math.max(...actual.porFranja);
  const iPico = actual.porFranja.indexOf(pico);
  const franjaPico: Franja = FRANJAS[iPico] ?? FRANJAS[0];

  return (
    <>
      <div className={estilos.radarFila}>
        <div className={`${estilos.vidrio} ${estilos.radarCaja}`}>
          <div>
            <h3>Radar de zonas</h3>
            <p className="secundario pequeno">Más cerca del centro = más pérdidas · el tamaño es el volumen · {textoFranja}</p>
          </div>
          <div className={estilos.radar}>
            <svg viewBox="0 0 100 100" className={estilos.radarFondo} aria-hidden="true">
              <circle cx="50" cy="50" r="48" />
              <circle cx="50" cy="50" r="36" strokeDasharray="1 1.2" />
              <circle cx="50" cy="50" r="24" />
              <circle cx="50" cy="50" r="11" className={estilos.radarCentro} />
              <path d="M50 2V98M2 50H98M16 16L84 84M84 16L16 84" className={estilos.radarEjes} />
            </svg>
            <div className={estilos.barrido} aria-hidden="true" />
            <span className={estilos.radarCritico} aria-hidden="true">CRÍTICO</span>
            {zonas.map((z) => (
              <button key={z.zona} type="button" className={`${estilos.nodo} ${claseNivel(z.nivel)} ${z.zona === actual.zona ? estilos.nodoActivo : ""}`}
                style={{ left: `${z.x}%`, top: `${z.y}%`, ["--d" as string]: `${Math.round(14 + z.peso * 24)}px` }}
                onClick={() => setElegida(z.zona)} aria-pressed={z.zona === actual.zona}
                aria-label={`${z.zona}: ${numero(z.valor)} pérdidas (${z.nivel.toLowerCase()})`}>
                <span className={estilos.punto} />
                <span className={estilos.ficha}>{z.zona} · <b>{numero(z.valor)}</b></span>
              </button>
            ))}
          </div>
        </div>

        <div className={`${estilos.vidrio} ${estilos.inspector}`} aria-live="polite">
          <div className={estilos.inspectorCabeza}>
            <h3>{actual.zona}</h3>
            <span className={`${estilos.pastilla} ${claseNivel(actual.nivel)}`}>{actual.nivel}</span>
          </div>
          <div className={estilos.dosCifras}>
            <div className={estilos.cifra}><p className="secundario pequeno">Pérdidas en el día</p><p className={estilos.cifraValor}>{numero(actual.total)}</p></div>
            <div className={estilos.cifra}><p className="secundario pequeno">Pico · {NOMBRE_FRANJA(franjaPico)}</p><p className={`${estilos.cifraValor} ${estilos.resalta}`}>{numero(pico)}</p></div>
          </div>
          <p className={estilos.etiqueta}>Pérdidas por franja horaria</p>
          <div className={estilos.barras}>
            {actual.porFranja.map((v, i) => (
              <div key={FRANJAS[i]} className={estilos.barraCol}>
                <span className={estilos.barraValor}>{numero(v)}</span>
                <div className={`${estilos.barraPista} ${franja === FRANJAS[i] ? estilos.barraElegida : ""}`}>
                  <div className={`${estilos.barra} ${i === iPico ? estilos.barraPico : ""}`} style={{ height: `${Math.max(6, (v / Math.max(1, pico)) * 100)}%` }} />
                </div>
                <span className="secundario pequeno">{(FRANJAS[i] ?? "").replace("-", "–")}</span>
              </div>
            ))}
          </div>
          <p className={estilos.consejo}>
            <b>Sugerencia</b> Reforzar rondas y avisos en {actual.zona.toLowerCase()} entre las {franjaPico.replace("-", " y las ")} h, que es cuando más se pierde.
          </p>
        </div>
      </div>

      <div className={`${estilos.vidrio} ${estilos.ranking}`}>
        <div className={estilos.rankingCabeza}>
          <h3>Ranking de zonas · {textoFranja}</h3>
          <p className="secundario pequeno">Toca una zona para ver su detalle</p>
        </div>
        <ol className={estilos.rankingLista}>
          {ranking.map((z, i) => (
            <li key={z.zona}>
              <button type="button" onClick={() => setElegida(z.zona)} aria-pressed={z.zona === actual.zona}
                className={`${estilos.rankingItem} ${z.zona === actual.zona ? estilos.rankingActivo : ""}`}>
                <span className={estilos.rankingFila}><span><b className={estilos.resalta}>{i + 1}</b> · {z.zona}</span><b>{numero(z.valor)}</b></span>
                <span className={estilos.pista}><span className={claseNivel(z.nivel)} style={{ width: `${Math.round(z.peso * 100)}%` }} /></span>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ categorías, embudo e IA
export function Categorias({ m }: { m: Informe["metricas"] }) {
  const lista = m.mes?.categorias ?? [];
  const tasa = m.mes?.tasa_recuperacion_pct ?? 0;
  const peor = lista[lista.length - 1];
  return (
    <div className={`${estilos.vidrio} ${estilos.tarjeta}`}>
      <div className={estilos.tarjetaCabeza}>
        <div><h3>Recuperación por categoría</h3><p className="secundario pequeno">Porcentaje devuelto a su dueño · {m.mes ? mesDePeriodo(m.mes.periodo) : ""}</p></div>
        <span className={estilos.pastilla}>{lista.length} rubros</span>
      </div>
      {lista.length === 0 ? (
        <p className="secundario">El próximo informe del agente traerá el detalle por categoría.</p>
      ) : (
        <div className={estilos.categorias}>
          <Anillo pct={tasa} tam={150} grosor={16}>
            <span className={estilos.anilloNumero}>{numero(tasa, 1)} %</span>
            <span className={estilos.anilloTexto}>GLOBAL</span>
          </Anillo>
          <ul className={estilos.listaCategorias}>
            {lista.map((c, i) => (
              <li key={c.categoria}>
                <span className={estilos.rankingFila}><span><i className={estilos.muestra} data-color={i % 6} />{c.categoria}</span><b>{numero(c.tasa_pct, 0)} %</b></span>
                <span className={estilos.pista}><span data-color={i % 6} style={{ width: `${c.tasa_pct}%` }} /></span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {peor && (
        <p className={estilos.nota}><b>Ojo:</b> {peor.categoria.toLowerCase()} es lo que menos vuelve ({numero(peor.tasa_pct, 1)} %).</p>
      )}
    </div>
  );
}

export function Embudo({ m }: { m: Informe["metricas"] }) {
  const e = m.embudo_mes;
  const precision = m.matching_4_semanas?.precision_pct;
  return (
    <div className={estilos.iaFila}>
      <div className={`${estilos.vidrio} ${estilos.tarjeta}`}>
        <div><h3>Del reporte a la entrega</h3><p className="secundario pequeno">Reportes de {m.mes ? mesDePeriodo(m.mes.periodo) : "el último mes"} según hasta dónde llegaron</p></div>
        {e ? (
          <ol className={estilos.embudo}>
            {pasosEmbudo(e).map((p, i) => (
              <li key={p.nombre}>
                <span className={estilos.rankingFila}><span>{p.nombre}</span><span><b>{numero(p.valor)}</b> <span className={estilos.resalta}>{p.pct} %</span></span></span>
                <span className={`${estilos.pista} ${estilos.pistaAlta}`}><span data-paso={i} style={{ width: `${Math.max(2, p.pct)}%` }} /></span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="secundario">El próximo informe del agente traerá el embudo del mes.</p>
        )}
      </div>
      {precision !== undefined && (
        <div className={`${estilos.vidrio} ${estilos.tarjeta} ${estilos.iaAnillo}`}>
          <Anillo pct={precision} tam={170} grosor={14}><span className={estilos.anilloNumero}>{numero(precision, 1)} %</span></Anillo>
          <p className="secundario pequeno">de {numero(m.matching_4_semanas!.sugeridas)} sugerencias</p>
          <p>de las sugerencias revisadas eran el objeto correcto. <b>La IA propone; la persona decide.</b></p>
        </div>
      )}
    </div>
  );
}

export function CifrasPrediccion({ p }: { p: Informe["prediccion"] }) {
  const pico = p.semanas.find((s) => s.clase === "parciales") ?? [...p.semanas].sort((a, b) => b.esperado - a.esperado)[0];
  return (
    <div className={estilos.tresCifras}>
      {p.backtest && <div className={estilos.cifra}><p className="secundario pequeno">Error de la predicción</p><p className={estilos.cifraValor}>{numero(p.backtest.mae_modelo, 1)}</p></div>}
      {p.backtest && <div className={estilos.cifra}><p className="secundario pequeno">Estimación simple</p><p className={`${estilos.cifraValor} ${estilos.azul}`}>{numero(p.backtest.mae_ingenuo, 1)}</p></div>}
      {pico && (
        <div className={`${estilos.cifra} ${estilos.cifraSenal}`}>
          <p className="secundario pequeno">{pico.clase === "parciales" ? "Próx. parciales (pico)" : "Semana más alta"}</p>
          <p className={`${estilos.cifraValor} ${estilos.resalta}`}>{fechaCorta(pico.semana_inicio)} · {numero(Math.round(pico.esperado))}</p>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ informe completo
export function InformeCompleto({ informe, abierto, onCerrar }: { informe: Informe; abierto: boolean; onCerrar: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);

  const m = informe.metricas, p = informe.prediccion;
  const semana = p.semanas[0];
  const pico = p.semanas.find((s) => s.clase === "parciales");
  const z = m.zonas_criticas ?? [];
  const puntos: { t: string; d: string }[] = [];
  if (z.length) {
    puntos.push({ t: "Puntos críticos por zona y horario", d: z.map((x) => `${x.zona} los ${x.dia} de ${NOMBRE_FRANJA(x.franja)} (${numero(x.perdidas)})`).join("; ") + ". Son los momentos con más pérdidas en el histórico." });
  }
  if (m.mes) {
    puntos.push({ t: "Recuperación", d: `En ${mesDePeriodo(m.mes.periodo)} se reportaron ${numero(m.mes.reportados)} objetos y se devolvieron ${numero(m.mes.recuperados)} (${numero(m.mes.tasa_recuperacion_pct, 1)} %${m.mes.tasa_mes_anterior_pct !== null ? `; el mes anterior fue ${numero(m.mes.tasa_mes_anterior_pct, 1)} %` : ""}). El tiempo típico hasta la entrega fue de ${numero(m.mes.dias_tipicos_hasta_recuperar, 1)} días.${m.mes.categoria_menos_recuperada ? ` Lo que menos vuelve: ${m.mes.categoria_menos_recuperada.categoria.toLowerCase()} (${numero(m.mes.categoria_menos_recuperada.tasa_pct, 1)} %).` : ""}` });
  }
  if (m.matching_4_semanas) {
    puntos.push({ t: "Aporte de la IA", d: `En las últimas 4 semanas la IA hizo ${numero(m.matching_4_semanas.sugeridas)} sugerencias; de las que el admin revisó, el ${numero(m.matching_4_semanas.precision_pct, 1)} % eran el objeto correcto. La IA propone; la decisión siempre es de la persona.` });
  }
  if (p.backtest) {
    puntos.push({ t: "Qué tan confiable es la predicción", d: `En las últimas ${p.backtest.semanas_evaluadas} semanas se equivocó en promedio ${numero(p.backtest.mae_modelo, 1)} objetos por semana; una estimación simple (promedio de 4 semanas) se equivocó ${numero(p.backtest.mae_ingenuo, 1)}.` });
  }
  if (z[0]) {
    puntos.push({ t: "Recomendación", d: `Reforzar rondas y avisos en ${z[0].zona.toLowerCase()} los ${z[0].dia} de ${NOMBRE_FRANJA(z[0].franja)}${pico ? ` y preparar el punto de entrega para la semana de parciales del ${fechaCorta(pico.semana_inicio)}` : ""}.` });
  }

  return (
    <dialog ref={ref} className={estilos.dialogo} onClose={onCerrar} aria-labelledby="informe-titulo"
      onClick={(e) => { if (e.target === e.currentTarget) onCerrar(); }}>
      <div className={estilos.dialogoCaja}>
        <div className={estilos.dialogoCabeza}>
          <div className={estilos.seccionTitulo}>
            <span className={estilos.iconoIa} aria-hidden="true">IA</span>
            <div>
              <h2 id="informe-titulo">Informe completo · agente analista</h2>
              <p className="secundario pequeno">{m.sede}{semana ? ` · semana del ${rangoSemana(semana.semana_inicio)}` : ""}</p>
            </div>
          </div>
          <button type="button" className={estilos.cerrar} onClick={onCerrar} aria-label="Cerrar">✕</button>
        </div>
        {semana && (
          <p className={estilos.proyeccion}>
            <b>Proyección semanal:</b> se esperan <b>{numero(Math.round(semana.esperado))} pérdidas</b> (rango probable{" "}
            {numero(semana.minimo_90)} a {numero(semana.maximo_90)}).
            {pico && pico !== semana && <> La semana del {fechaCorta(pico.semana_inicio)}, de parciales, sube a un pico estimado de <b>{numero(Math.round(pico.esperado))}</b>.</>}
          </p>
        )}
        <p className={estilos.dialogoResumen}>{informe.resumen}</p>
        <ol className={estilos.puntos}>
          {puntos.map((x, i) => (
            <li key={x.t}>
              <span className={estilos.puntoN} aria-hidden="true">{i + 1}</span>
              <div><p className={estilos.hallazgoTitulo}>{x.t}</p><p className="secundario">{x.d}</p></div>
            </li>
          ))}
        </ol>
        <div className={estilos.dialogoPie}>
          <p className="secundario pequeno">
            {informe.resumen_fuente === "llm" ? "✓ Cada cifra del resumen se comprobó contra los datos." : "Resumen con plantilla automática."}
            {p.backtest ? ` Error del modelo: ${numero(p.backtest.mae_modelo, 1)} objetos por semana.` : ""}
          </p>
          <button type="button" className={estilos.botonSenal} onClick={onCerrar}>Entendido</button>
        </div>
      </div>
    </dialog>
  );
}
