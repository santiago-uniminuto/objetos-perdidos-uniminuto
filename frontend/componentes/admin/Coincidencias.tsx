"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAviso } from "@/componentes/ui/Avisos";
import { Vacio } from "@/componentes/ui/Basicos";
import { Confirmar } from "@/componentes/ui/Confirmar";
import { Foto } from "@/componentes/ui/Foto";
import { api, ErrorApi, urlFoto } from "@/lib/api";
import { leerExplicacion } from "@/lib/explicacion";
import { fechaCorta, haceCuanto, numero } from "@/lib/formato";

import estilos from "./Coincidencias.module.css";

export type Par = {
  id: string;
  creado_en: string;
  estado: "sugerida" | "verificada" | "rechazada" | "entregada";
  puntaje: number | string;
  similitud: number;
  explicacion: string | null;
  decidido_en: string | null;
  motivo_rechazo: string | null;
  reporte_id: string;
  reporte: string;
  fecha_perdida: string;
  reporte_hora: string | null;
  reporte_categoria: string;
  reporte_zona: string | null;
  reporte_fotos: string[];
  hallazgo_id: string;
  hallazgo: string;
  hallazgo_detalle: string;
  fecha_hallazgo: string;
  hallazgo_hora: string | null;
  ubicacion_bodega: string | null;
  hallazgo_categoria: string;
  hallazgo_zona: string | null;
  hallazgo_fotos: string[];
};

const PESTANAS = [
  { estado: "sugerida", nombre: "Por revisar" },
  { estado: "verificada", nombre: "Por entregar" },
  { estado: "entregada", nombre: "Entregadas" },
  { estado: "rechazada", nombre: "Rechazadas" },
] as const;
const UMBRAL = 0.6; // ADR-013: por debajo, el matcher no sugiere
const MOTIVOS = ["Otro color", "Otra marca o modelo", "Otro tipo de objeto", "Las fechas no cuadran", "Detalle distinto"];

export function BandejaCoincidencias() {
  const avisar = useAviso();
  const [estado, setEstado] = useState<(typeof PESTANAS)[number]["estado"]>("sugerida");
  const [pares, setPares] = useState<Par[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aVerificar, setAVerificar] = useState<Par | null>(null);
  const [aRechazar, setARechazar] = useState<Par | null>(null);
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [saliendo, setSaliendo] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      setPares((await api<{ items: Par[] }>(`/coincidencias?estado=${estado}&limite=100`)).items);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo cargar la bandeja.");
    }
  }, [estado]);
  useEffect(() => { setPares(null); void cargar(); }, [cargar]);

  /** La tarjeta decidida sale de la lista con una transición corta: se ve qué cambió */
  async function decidir(par: Par, accion: "verificar" | "rechazar") {
    setOcupado(true);
    try {
      await api(`/coincidencias/${par.id}/${accion}`, { method: "POST", json: accion === "rechazar" ? { motivo: motivo.trim() } : undefined });
      avisar("ok", accion === "verificar" ? "Coincidencia verificada. Se avisará al dueño por correo." : "Sugerencia rechazada.");
      setAVerificar(null);
      setARechazar(null);
      setMotivo("");
      setSaliendo(par.id);
      setTimeout(() => { setPares((p) => p?.filter((x) => x.id !== par.id) ?? null); setSaliendo(null); }, 220);
    } catch (e) {
      avisar("error", e instanceof ErrorApi ? e.message : "No se pudo guardar la decisión.");
      if (e instanceof ErrorApi && e.estado === 409) void cargar();
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={estilos.pagina}>
      <header>
        <h1>Coincidencias</h1>
        <p className="secundario">La IA propone pares parecidos; tú decides. Ninguna sugerencia se entrega sin tu verificación.</p>
      </header>
      <div className={estilos.pestanas} role="tablist" aria-label="Estado">
        {PESTANAS.map((p) => (
          <button key={p.estado} role="tab" aria-selected={estado === p.estado} onClick={() => setEstado(p.estado)}>
            {p.nombre}
          </button>
        ))}
      </div>

      {error && <p className="aviso aviso-error" role="alert">{error}</p>}
      {pares === null && !error && <div className="esqueleto" style={{ height: "18rem" }} aria-busy="true" />}
      {pares?.length === 0 && (
        <Vacio titulo={estado === "sugerida" ? "No hay sugerencias por revisar" : estado === "verificada" ? "No hay objetos por entregar" : "Nada por aquí todavía"}>
          {estado === "sugerida" ? "Cuando el agente encuentre un hallazgo parecido a un reporte, aparecerá aquí." : undefined}
        </Vacio>
      )}

      <ul className={estilos.lista}>
        {pares?.map((par) => (
          <li key={par.id} className={estilos.par} data-saliendo={saliendo === par.id || undefined}>
            <Lado titulo="Reportado como perdido" categoria={par.reporte_categoria} descripcion={par.reporte}
              zona={par.reporte_zona} fecha={par.fecha_perdida} hora={par.reporte_hora} fotos={par.reporte_fotos} />
            <Veredicto par={par} />
            <Lado titulo="Encontrado" categoria={par.hallazgo_categoria} descripcion={par.hallazgo}
              detalle={par.hallazgo_detalle !== par.hallazgo ? par.hallazgo_detalle : undefined}
              zona={par.hallazgo_zona} fecha={par.fecha_hallazgo} hora={par.hallazgo_hora} fotos={par.hallazgo_fotos}
              extra={par.ubicacion_bodega ? `Bodega: ${par.ubicacion_bodega}` : undefined} />
            <div className={estilos.acciones}>
              {par.estado === "sugerida" && <>
                <button className="boton boton-borde" onClick={() => setARechazar(par)}>Rechazar</button>
                <button className="boton boton-senal" onClick={() => setAVerificar(par)}>Es el mismo objeto</button>
              </>}
              {par.estado === "verificada" && (
                <Link className="boton boton-senal" href={`/admin/entregas/nueva/?coincidencia=${par.id}`}>Registrar entrega</Link>
              )}
              {(par.estado === "rechazada" || par.estado === "entregada") && (
                <p className="secundario pequeno">
                  {par.estado === "rechazada" ? `Rechazada: ${par.motivo_rechazo ?? "sin motivo"}` : "Entregada al dueño"}
                  {par.decidido_en && `, ${haceCuanto(par.decidido_en)}`}
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>

      <Confirmar abierto={!!aVerificar} titulo="¿Es el mismo objeto?" accion="Sí, verificar" ocupado={ocupado}
        onConfirmar={() => aVerificar && void decidir(aVerificar, "verificar")} onCancelar={() => setAVerificar(null)}>
        El reporte y el hallazgo quedan unidos y el dueño recibe un correo para que venga a reclamarlo.
        La entrega se hace aparte, verificando su carné y la pregunta de control.
      </Confirmar>
      <Confirmar abierto={!!aRechazar} titulo="Rechazar la sugerencia" accion="Rechazar" peligro ocupado={ocupado}
        onConfirmar={() => {
          if (motivo.trim().length < 3) return avisar("error", "Escribe o elige un motivo (mínimo 3 caracteres).");
          if (aRechazar) void decidir(aRechazar, "rechazar");
        }}
        onCancelar={() => { setARechazar(null); setMotivo(""); }}>
        <p>El motivo ayuda a medir y mejorar la IA. El par no se volverá a sugerir.</p>
        <div className={estilos.motivos}>
          {MOTIVOS.map((m) => (
            <button key={m} type="button" className="boton boton-chico boton-borde" aria-pressed={motivo === m} onClick={() => setMotivo(m)}>{m}</button>
          ))}
        </div>
        <label className="campo" style={{ marginTop: "0.8rem" }}>
          <span>Motivo</span>
          <input value={motivo} maxLength={300} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: el termo hallado es rojo" />
        </label>
      </Confirmar>
    </div>
  );
}

function Lado({ titulo, categoria, descripcion, detalle, zona, fecha, hora, fotos, extra }: {
  titulo: string; categoria: string; descripcion: string; detalle?: string; zona: string | null; fecha: string;
  hora: string | null; fotos: string[]; extra?: string;
}) {
  return (
    <section className={estilos.lado}>
      <p className={estilos.ladoTitulo}>{titulo}</p>
      {fotos[0] ? (
        <Foto className={estilos.foto} src={urlFoto(fotos[0])} alt={`Foto: ${descripcion}`} loading="lazy"
          respaldo={<div className={estilos.sinFoto}>Sin foto</div>} />
      ) : <div className={estilos.sinFoto}>Sin foto</div>}
      <h3>{categoria}</h3>
      <p>{descripcion}</p>
      {detalle && <p className="secundario pequeno">{detalle}</p>}
      <p className="secundario pequeno">
        {zona ?? "Sin zona"}, {fechaCorta(fecha)}{hora ? ` a las ${hora.slice(0, 5)}` : ""}
      </p>
      {extra && <p className="pequeno"><strong>{extra}</strong></p>}
    </section>
  );
}

/** El centro del par: qué tan parecidos son y por qué, según la IA. El medidor marca el umbral de sugerencia. */
function Veredicto({ par }: { par: Par }) {
  const puntaje = Number(par.puntaje);
  const e = leerExplicacion(par.explicacion);
  return (
    <section className={estilos.veredicto} aria-label="Análisis de la IA">
      <p className={estilos.porcentaje}>{numero(puntaje * 100)} %</p>
      <p className="secundario pequeno">de parecido</p>
      <div className={estilos.medidor} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(puntaje * 100)}
        aria-label="Puntaje de parecido">
        <span style={{ width: `${Math.min(100, puntaje * 100)}%` }} />
        <i style={{ left: `${UMBRAL * 100}%` }} title="Umbral para sugerir (60 %)" />
      </div>
      {e ? (
        <div className={estilos.explicacion}>
          {e.confianza && <p className="pequeno"><strong>Confianza {e.confianza}</strong></p>}
          {e.texto && <p className="pequeno">{e.texto}</p>}
          {e.coincide.length > 0 && <p className="pequeno"><span className={estilos.si}>Coincide:</span> {e.coincide.join(", ")}</p>}
          {e.difiere.length > 0 && <p className="pequeno"><span className={estilos.no}>Difiere:</span> {e.difiere.join(", ")}</p>}
        </div>
      ) : <p className="secundario pequeno">Sin explicación de la IA para este par.</p>}
    </section>
  );
}
