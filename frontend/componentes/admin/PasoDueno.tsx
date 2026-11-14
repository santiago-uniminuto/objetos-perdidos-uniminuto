"use client";

import { useState } from "react";

import { Campo } from "@/componentes/ui/Basicos";
import { api, ErrorApi, type Estudiante } from "@/lib/api";

import estilos from "./Formulario.module.css";

/** Paso 1 del reporte de pérdida: identificar al dueño y su consentimiento (Ley 1581).
 *  Buscar primero evita duplicados; crear solo si no existe. */
export function PasoDueno({ onListo }: { onListo: (e: Estudiante) => void }) {
  const [tipo, setTipo] = useState("CC");
  const [numero, setNumero] = useState("");
  const [encontrado, setEncontrado] = useState<Estudiante | null>(null);
  const [nuevo, setNuevo] = useState(false);
  const [datos, setDatos] = useState({ nombres: "", apellidos: "", correo_institucional: "", telefono: "" });
  const [acepta, setAcepta] = useState({ gestion: false, correo: true });
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function buscar() {
    setError(null);
    setEncontrado(null);
    setNuevo(false);
    if (!/^[A-Za-z0-9]{4,20}$/.test(numero)) return setError("Escribe el número de documento sin puntos ni espacios.");
    setOcupado(true);
    try {
      const q = new URLSearchParams({ tipo_documento: tipo, numero_documento: numero, motivo: "registro de reporte" });
      setEncontrado(await api<Estudiante>(`/estudiantes?${q}`));
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 404) setNuevo(true);
      else setError(e instanceof ErrorApi ? e.message : "No se pudo buscar.");
    } finally {
      setOcupado(false);
    }
  }

  async function continuar() {
    setError(null);
    if (!acepta.gestion && !encontrado?.consentimiento_vigente)
      return setError("Sin la autorización del estudiante no podemos guardar sus datos ni gestionar su objeto.");
    setOcupado(true);
    try {
      let est = encontrado;
      if (!est) {
        const creado = await api<Estudiante>("/estudiantes", { method: "POST", json: {
          tipo_documento: tipo, numero_documento: numero, nombres: datos.nombres.trim(), apellidos: datos.apellidos.trim(),
          correo_institucional: datos.correo_institucional.trim() || null, telefono: datos.telefono.trim() || null,
        } });
        est = { ...creado, consentimiento_vigente: null };
      }
      if (!est.consentimiento_vigente) {
        const finalidades = ["gestion_objeto", ...(acepta.correo ? ["notificacion_correo"] : [])];
        await api("/consentimientos", { method: "POST", json: { estudiante_id: est.id, finalidades, canal: "presencial" } });
        est = { ...est, consentimiento_vigente: { finalidades, otorgado_en: new Date().toISOString() } };
      }
      onListo(est);
    } catch (e) {
      setError(e instanceof ErrorApi ? (e.estado === 422 ? "Revisa los datos: hay campos con formato inválido." : e.message)
        : "No se pudo guardar.");
    } finally {
      setOcupado(false);
    }
  }

  const listoParaSeguir = encontrado ? !encontrado.anonimizado_en : nuevo && datos.nombres.trim() && datos.apellidos.trim();

  return (
    <div className={estilos.paso}>
      <form className={estilos.fila} onSubmit={(e) => { e.preventDefault(); void buscar(); }}>
        <Campo etiqueta="Documento">
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="CC">Cédula</option>
            <option value="TI">Tarjeta de identidad</option>
            <option value="CE">Cédula de extranjería</option>
            <option value="PPT">PPT</option>
            <option value="PA">Pasaporte</option>
          </select>
        </Campo>
        <Campo etiqueta="Número">
          <input inputMode="numeric" autoComplete="off" value={numero} onChange={(e) => setNumero(e.target.value.trim())} />
        </Campo>
        <button className="boton boton-borde" disabled={ocupado}>Buscar</button>
      </form>

      {encontrado && (
        <div className={estilos.ficha}>
          <p><strong>{encontrado.nombres} {encontrado.apellidos}</strong></p>
          <p className="secundario">{encontrado.correo_institucional ?? "Sin correo registrado: no recibirá avisos"}</p>
          {encontrado.anonimizado_en && <p className="aviso aviso-error">Este estudiante pidió borrar sus datos.</p>}
          {encontrado.consentimiento_vigente && <p className="secundario pequeno">Ya autorizó el tratamiento de sus datos.</p>}
        </div>
      )}

      {nuevo && (
        <div className={estilos.paso}>
          <p className="secundario">No está registrado. Completa sus datos:</p>
          <div className={estilos.dosColumnas}>
            <Campo etiqueta="Nombres"><input value={datos.nombres} onChange={(e) => setDatos({ ...datos, nombres: e.target.value })} /></Campo>
            <Campo etiqueta="Apellidos"><input value={datos.apellidos} onChange={(e) => setDatos({ ...datos, apellidos: e.target.value })} /></Campo>
            <Campo etiqueta="Correo institucional" ayuda="Para avisarle si aparece su objeto">
              <input type="email" value={datos.correo_institucional} onChange={(e) => setDatos({ ...datos, correo_institucional: e.target.value })} />
            </Campo>
            <Campo etiqueta="Celular (opcional)">
              <input type="tel" value={datos.telefono} onChange={(e) => setDatos({ ...datos, telefono: e.target.value })} />
            </Campo>
          </div>
        </div>
      )}

      {(nuevo || (encontrado && !encontrado.consentimiento_vigente && !encontrado.anonimizado_en)) && (
        <fieldset className={estilos.consentimiento}>
          <legend>Autorización (Ley 1581 de 2012)</legend>
          <label><input type="checkbox" checked={acepta.gestion} onChange={(e) => setAcepta({ ...acepta, gestion: e.target.checked })} />
            {" "}El estudiante leyó el aviso de privacidad y autoriza usar sus datos para gestionar su objeto.</label>
          <label><input type="checkbox" checked={acepta.correo} onChange={(e) => setAcepta({ ...acepta, correo: e.target.checked })} />
            {" "}Autoriza recibir avisos en su correo institucional.</label>
        </fieldset>
      )}

      {error && <p className="aviso aviso-error" role="alert">{error}</p>}
      {listoParaSeguir && (
        <div><button className="boton boton-senal" onClick={() => void continuar()} disabled={ocupado}>
          {ocupado ? "Guardando…" : "Continuar"}
        </button></div>
      )}
    </div>
  );
}
