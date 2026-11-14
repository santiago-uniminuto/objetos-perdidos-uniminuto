"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { PasoDueno } from "@/componentes/admin/PasoDueno";
import { useUsuario } from "@/componentes/admin/Sesion";
import { Campo, Pasos } from "@/componentes/ui/Basicos";
import { PlanoZonas } from "@/componentes/ui/PlanoZonas";
import { SubirFotos } from "@/componentes/ui/SubirFotos";
import { api, type Catalogos, crear, ErrorApi, type Estudiante, subirFoto } from "@/lib/api";

import estilos from "./Formulario.module.css";

type Tipo = "perdido" | "hallado";
const hoy = () => new Date().toLocaleDateString("en-CA"); // AAAA-MM-DD en hora local

/** Registro de un reporte de pérdida o de un hallazgo en pasos cortos.
 *  El paso del dueño solo existe para lo perdido; lo hallado no tiene dueño todavía. */
export function FormularioObjeto({ tipo }: { tipo: Tipo }) {
  const usuario = useUsuario();
  const pasos = tipo === "perdido"
    ? ["Dueño", "Qué es", "Dónde y cuándo", "Descripción y fotos"]
    : ["Qué es", "Dónde y cuándo", "Descripción y fotos"];
  const [paso, setPaso] = useState(0);
  const nombre = pasos[paso];
  const [catalogos, setCatalogos] = useState<Catalogos | null>(null);
  const [dueno, setDueno] = useState<Estudiante | null>(null);
  const [f, setF] = useState({ categoria_id: 0, zona_id: null as number | null, fecha: hoy(), hora: "",
    descripcion: "", descripcion_publica: "", detalle_control: "", encontrado_por: "", ubicacion_bodega: "" });
  const [fotos, setFotos] = useState<File[]>([]);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [estado, setEstado] = useState<"editando" | "enviando" | "listo">("editando");
  const [progreso, setProgreso] = useState("");
  const [resultado, setResultado] = useState<{ id: string; fotosFallidas: number } | null>(null);
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  // Una clave por intento de registro: si se reintenta el envío, la API no duplica el objeto
  const clave = useMemo(() => crypto.randomUUID(), []);

  useEffect(() => { api<Catalogos>("/catalogos").then(setCatalogos).catch(() => setCatalogos(null)); }, []);
  const zonas = catalogos?.zonas.filter((z) => z.sede_id === usuario.sede_id) ?? [];
  const categoria = catalogos?.categorias.find((c) => c.id === f.categoria_id);

  function validar(): boolean {
    const e: Record<string, string> = {};
    if (nombre === "Qué es" && !f.categoria_id) e.categoria = "Elige una categoría.";
    if (nombre === "Dónde y cuándo") {
      if (!f.fecha) e.fecha = "Indica la fecha.";
      else if (f.fecha > hoy()) e.fecha = "La fecha no puede ser futura.";
    }
    if (nombre === "Descripción y fotos") {
      if (f.descripcion_publica.trim().length < 5) e.descripcion_publica = "Escribe al menos 5 caracteres.";
      if (f.descripcion.trim().length < 5) e.descripcion = "Escribe al menos 5 caracteres.";
    }
    setErrores(e);
    return Object.keys(e).length === 0;
  }

  async function registrar() {
    if (!validar()) return;
    setEstado("enviando");
    setErrorEnvio(null);
    const comun = { categoria_id: f.categoria_id, zona_id: f.zona_id, descripcion: f.descripcion.trim(),
      descripcion_publica: f.descripcion_publica.trim(), hora_aprox: f.hora || null };
    try {
      setProgreso("Guardando el registro…");
      const creado = tipo === "perdido"
        ? await crear<{ id: string }>("/reportes", { ...comun, estudiante_id: dueno!.id, fecha_perdida: f.fecha,
            detalle_control: f.detalle_control.trim() || null }, clave)
        : await crear<{ id: string }>("/hallazgos", { ...comun, fecha_hallazgo: f.fecha,
            encontrado_por: f.encontrado_por.trim() || null, ubicacion_bodega: f.ubicacion_bodega.trim() || null }, clave);
      let fallidas = 0;
      for (const [i, archivo] of fotos.entries()) {
        setProgreso(`Subiendo foto ${i + 1} de ${fotos.length}…`);
        try { await subirFoto(tipo === "perdido" ? "reportes" : "hallazgos", creado.id, archivo); } catch { fallidas += 1; }
      }
      setResultado({ id: creado.id, fotosFallidas: fallidas });
      setEstado("listo");
    } catch (e) {
      setErrorEnvio(e instanceof ErrorApi ? e.message : "No se pudo registrar. Revisa la conexión e intenta de nuevo.");
      setEstado("editando");
    }
  }

  if (estado === "listo" && resultado) {
    const base = tipo === "perdido" ? "/admin/reportes" : "/admin/hallazgos";
    return (
      <div className={estilos.exito}>
        <p className={estilos.exitoTitulo} aria-live="polite">
          {(tipo === "perdido" ? "Reporte registrado" : "Hallazgo registrado").split(" ").map((p, i) => (
            <span key={p} style={{ animationDelay: `${i * 90}ms` }}>{p}</span>
          ))}
        </p>
        <p className="secundario">
          {tipo === "perdido"
            ? "Ya aparece en el portal público y el agente de coincidencias lo está comparando con lo hallado."
            : "El agente de coincidencias lo está comparando con los reportes de pérdida. No se publica."}
        </p>
        {resultado.fotosFallidas > 0 && (
          <p className="aviso aviso-error">{resultado.fotosFallidas} foto(s) no se pudieron subir. Agrégalas desde el detalle.</p>
        )}
        <div className={estilos.acciones}>
          <Link className="boton" href={`${base}/ver/?id=${resultado.id}`}>Ver el registro</Link>
          <button className="boton boton-borde" onClick={() => window.location.reload()}>Registrar otro</button>
        </div>
      </div>
    );
  }

  return (
    <div className={estilos.formulario}>
      <Pasos pasos={pasos} actual={paso} />

      {nombre === "Dueño" && (
        dueno ? (
          <div className={estilos.paso}>
            <div className={estilos.ficha}>
              <p><strong>{dueno.nombres} {dueno.apellidos}</strong>, {dueno.tipo_documento} {dueno.numero_documento}</p>
            </div>
            <div><button className="boton boton-borde boton-chico" onClick={() => setDueno(null)}>Cambiar de estudiante</button></div>
          </div>
        ) : <PasoDueno onListo={(e) => { setDueno(e); setPaso(1); }} />
      )}

      {nombre === "Qué es" && (
        <fieldset className={estilos.categorias}>
          <legend className="visualmente-oculto">Categoría</legend>
          {catalogos?.categorias.map((c) => (
            <label key={c.id} data-elegida={f.categoria_id === c.id || undefined}>
              <input type="radio" name="categoria" checked={f.categoria_id === c.id} onChange={() => setF({ ...f, categoria_id: c.id })} />
              <span>{c.nombre}</span>
            </label>
          ))}
          {errores.categoria && <p className="error" style={{ color: "var(--error)", fontWeight: 700 }}>{errores.categoria}</p>}
        </fieldset>
      )}

      {nombre === "Dónde y cuándo" && (
        <div className={estilos.paso}>
          <PlanoZonas zonas={zonas} valor={f.zona_id} onCambio={(zona_id) => setF({ ...f, zona_id })} />
          <div className={estilos.dosColumnas}>
            <Campo etiqueta={tipo === "perdido" ? "Fecha en que lo perdió" : "Fecha en que se encontró"} error={errores.fecha}>
              <input type="date" max={hoy()} value={f.fecha} onChange={(e) => setF({ ...f, fecha: e.target.value })} />
            </Campo>
            <Campo etiqueta="Hora aproximada (opcional)" ayuda="Ayuda al mapa de calor y al cruce">
              <input type="time" value={f.hora} onChange={(e) => setF({ ...f, hora: e.target.value })} />
            </Campo>
          </div>
        </div>
      )}

      {nombre === "Descripción y fotos" && (
        <div className={estilos.paso}>
          <Campo etiqueta={tipo === "perdido" ? "Descripción pública" : "Descripción corta"} error={errores.descripcion_publica}
            ayuda={tipo === "perdido" ? "Sale en el portal. Sin nombres, documentos ni teléfonos. Ej.: Termo azul con sticker."
              : "Para identificarlo en las listas (lo hallado no se publica). Ej.: Termo azul metálico."}>
            <input maxLength={300} value={f.descripcion_publica} onChange={(e) => setF({ ...f, descripcion_publica: e.target.value })} />
          </Campo>
          <Campo etiqueta="Descripción completa" error={errores.descripcion} ayuda="Marca, color, detalles. La IA la usa para buscar coincidencias, sin datos personales.">
            <textarea rows={3} maxLength={1000} value={f.descripcion} onChange={(e) => setF({ ...f, descripcion: e.target.value })} />
          </Campo>
          {tipo === "perdido" ? (
            <Campo etiqueta="Detalle de control (secreto)" ayuda="Algo que solo el dueño sabe. Se le pregunta al entregar; nunca se publica.">
              <input maxLength={300} value={f.detalle_control} onChange={(e) => setF({ ...f, detalle_control: e.target.value })} />
            </Campo>
          ) : (
            <div className={estilos.dosColumnas}>
              <Campo etiqueta="Ubicación en bodega" ayuda="Ej.: Estante A3">
                <input maxLength={60} value={f.ubicacion_bodega} onChange={(e) => setF({ ...f, ubicacion_bodega: e.target.value })} />
              </Campo>
              <Campo etiqueta="Quién lo entregó (opcional)">
                <input maxLength={120} value={f.encontrado_por} onChange={(e) => setF({ ...f, encontrado_por: e.target.value })} />
              </Campo>
            </div>
          )}
          <div className="campo">
            <span>Fotos (opcional)</span>
            <SubirFotos archivos={fotos} onCambio={setFotos} aviso={
              tipo === "hallado" ? "Las fotos de lo hallado nunca se publican."
                : categoria?.es_documento ? "Esta categoría es un documento: sus fotos no se publican."
                : "Se mostrarán en el portal: evita caras, nombres o documentos en la foto."} />
          </div>
        </div>
      )}

      {errorEnvio && <p className="aviso aviso-error" role="alert">{errorEnvio}</p>}

      {nombre !== "Dueño" && (
        <div className={estilos.acciones}>
          {paso > 0 && <button className="boton boton-borde" onClick={() => setPaso(paso - 1)} disabled={estado === "enviando"}>Atrás</button>}
          {paso < pasos.length - 1 ? (
            <button className="boton boton-senal" onClick={() => validar() && setPaso(paso + 1)}>Siguiente</button>
          ) : (
            <button className="boton boton-senal" onClick={() => void registrar()} disabled={estado === "enviando"}>
              {estado === "enviando" ? progreso : tipo === "perdido" ? "Registrar pérdida" : "Registrar hallazgo"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
