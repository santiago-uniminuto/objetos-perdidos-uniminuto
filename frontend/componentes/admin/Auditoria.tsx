"use client";

import { useCallback, useEffect, useState } from "react";

import { Vacio } from "@/componentes/ui/Basicos";
import { api, ErrorApi } from "@/lib/api";
import { fechaLarga } from "@/lib/formato";

import estilos from "./Auditoria.module.css";

type Registro = {
  id: string; creado_en: string; accion: string; entidad: string; entidad_id: string | null; sede_id: number | null;
  motivo: string | null; ip: string | null; detalle: Record<string, unknown> | null; usuario: string | null;
};

const ACCIONES: Record<string, string> = {
  leer: "Leyó datos personales", crear: "Creó", actualizar: "Actualizó", anonimizar: "Anonimizó", login: "Inició sesión",
  login_fallido: "Intento de ingreso fallido", exportar: "Exportó", cambio_contrasena: "Cambió la contraseña",
  solicitud_restablecimiento: "Pidió restablecer la contraseña",
};
const ENTIDADES: Record<string, string> = {
  reporte_perdida: "reporte", hallazgo: "hallazgo", estudiante: "estudiante", coincidencia: "coincidencia",
  entrega: "entrega", usuario: "cuenta", consentimiento: "consentimiento", foto_objeto: "foto",
};

/** Bitácora para el rol auditor: tabla densa con filtros. Solo consulta; no se puede editar ni borrar. */
export function Auditoria() {
  const [filtros, setFiltros] = useState({ accion: "", entidad: "", desde: "", hasta: "" });
  const [filas, setFilas] = useState<Registro[] | null>(null);
  const [siguiente, setSiguiente] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async (cursor: string | null) => {
    setError(null);
    const q = new URLSearchParams({ limite: "50" });
    Object.entries(filtros).forEach(([k, v]) => v && q.set(k, v));
    if (cursor) q.set("cursor", cursor);
    try {
      const r = await api<{ items: Registro[]; siguiente: string | null }>(`/auditoria?${q}`);
      setFilas((p) => (cursor && p ? [...p, ...r.items] : r.items));
      setSiguiente(r.siguiente);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo cargar la auditoría.");
    }
  }, [filtros]);
  useEffect(() => { setFilas(null); void cargar(null); }, [cargar]);

  const cambiar = (k: keyof typeof filtros) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setFiltros((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className={estilos.pagina}>
      <header>
        <h1>Auditoría</h1>
        <p className="secundario">Quién hizo qué y cuándo. Los registros no se pueden modificar ni borrar.</p>
      </header>
      <div className={estilos.filtros}>
        <label className="campo"><span>Acción</span>
          <select value={filtros.accion} onChange={cambiar("accion")}>
            <option value="">Todas</option>
            {Object.entries(ACCIONES).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </label>
        <label className="campo"><span>Sobre</span>
          <select value={filtros.entidad} onChange={cambiar("entidad")}>
            <option value="">Todo</option>
            {Object.entries(ENTIDADES).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </label>
        <label className="campo"><span>Desde</span><input type="date" value={filtros.desde} onChange={cambiar("desde")} /></label>
        <label className="campo"><span>Hasta</span><input type="date" value={filtros.hasta} onChange={cambiar("hasta")} /></label>
      </div>

      {error && <p className="aviso aviso-error" role="alert">{error}</p>}
      {filas === null && !error && <div className="esqueleto" style={{ height: "16rem" }} aria-busy="true" />}
      {filas?.length === 0 && <Vacio titulo="No hay registros con esos filtros" />}
      {filas && filas.length > 0 && (
        <div className={estilos.tablaCaja}>
          <table className={estilos.tabla}>
            <thead>
              <tr><th>Cuándo</th><th>Quién</th><th>Qué</th><th>Sobre</th><th>Motivo o detalle</th><th>IP</th></tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.id} data-sensible={f.accion === "leer" || f.accion === "login_fallido" || undefined}>
                  <td title={f.creado_en}>{fechaLarga(f.creado_en)}<br /><span className="secundario">{new Date(f.creado_en).toLocaleTimeString("es-CO")}</span></td>
                  <td>{f.usuario ?? "Sistema"}</td>
                  <td>{ACCIONES[f.accion] ?? f.accion}</td>
                  <td>{ENTIDADES[f.entidad] ?? f.entidad}{f.sede_id ? `, sede ${f.sede_id}` : ""}</td>
                  <td>{f.motivo ?? (f.detalle ? Object.entries(f.detalle).map(([k, v]) => `${k}: ${String(v)}`).join("; ") : "")}</td>
                  <td className={estilos.ip}>{f.ip?.replace(/\/(32|128)$/, "") ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {siguiente && <div><button className="boton boton-borde" onClick={() => void cargar(siguiente)}>Ver más</button></div>}
    </div>
  );
}
