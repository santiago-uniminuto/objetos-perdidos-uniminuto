"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAviso } from "@/componentes/ui/Avisos";
import { Insignia, Vacio } from "@/componentes/ui/Basicos";
import { Confirmar } from "@/componentes/ui/Confirmar";
import { Foto } from "@/componentes/ui/Foto";
import { MAX_FOTOS, SubirFotos } from "@/componentes/ui/SubirFotos";
import { api, ErrorApi, type FotoInfo, type ObjetoDetalle, type ObjetoLista, subirFoto, urlFoto } from "@/lib/api";
import { fechaLarga, haceCuanto } from "@/lib/formato";

import estilos from "./Objetos.module.css";

type Tipo = "perdido" | "hallado";
const RUTA = { perdido: "reportes", hallado: "hallazgos" } as const;
const ABIERTOS = new Set(["registrado", "publicado", "en_coincidencia"]);

// ------------------------------------------------------------------ lista
export function ListaObjetos({ tipo }: { tipo: Tipo }) {
  const ruta = RUTA[tipo];
  const [estado, setEstado] = useState("");
  const [items, setItems] = useState<ObjetoLista[] | null>(null);
  const [siguiente, setSiguiente] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async (cursor: string | null) => {
    setError(null);
    const q = new URLSearchParams({ limite: "20" });
    if (estado) q.set("estado", estado);
    if (cursor) q.set("cursor", cursor);
    try {
      const r = await api<{ items: ObjetoLista[]; siguiente: string | null }>(`/${ruta}?${q}`);
      setItems((prev) => (cursor && prev ? [...prev, ...r.items] : r.items));
      setSiguiente(r.siguiente);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo cargar la lista.");
    }
  }, [estado, ruta]);

  useEffect(() => { setItems(null); void cargar(null); }, [cargar]);

  const titulo = tipo === "perdido" ? "Reportes de pérdida" : "Hallazgos";
  return (
    <div className={estilos.pagina}>
      <header className={estilos.cabecera}>
        <h1>{titulo}</h1>
        <Link className="boton boton-senal" href={`/admin/${ruta}/nuevo/`}>
          {tipo === "perdido" ? "Registrar pérdida" : "Registrar hallazgo"}
        </Link>
      </header>
      <div className={estilos.filtro} role="group" aria-label="Filtrar por estado">
        {[["", "Todos"], ["publicado", tipo === "perdido" ? "Publicados" : "En custodia"], ["en_coincidencia", "Con coincidencia"],
          ["entregado", "Entregados"]].map(([v, n]) => (
          <button key={v} className="boton boton-chico boton-borde" aria-pressed={estado === v} onClick={() => setEstado(v!)}>{n}</button>
        ))}
      </div>

      {error && <p className="aviso aviso-error" role="alert">{error}</p>}
      {items === null && !error && (
        <div className={estilos.lista} aria-busy="true">
          {[0, 1, 2, 3].map((i) => <div key={i} className="esqueleto" style={{ height: "4.6rem" }} />)}
        </div>
      )}
      {items && items.length === 0 && (
        <Vacio titulo={estado ? "No hay registros con ese estado" : tipo === "perdido" ? "Aún no hay reportes" : "Aún no hay hallazgos"}
          accion={!estado && <Link className="boton" href={`/admin/${ruta}/nuevo/`}>{tipo === "perdido" ? "Registrar el primero" : "Registrar el primero"}</Link>}>
          {tipo === "perdido" ? "Cuando un estudiante reporte algo, aparecerá aquí." : "Lo que entreguen en la oficina se registra aquí."}
        </Vacio>
      )}
      {items && items.length > 0 && (
        <ul className={estilos.lista}>
          {items.map((o) => {
            const fecha = o.fecha_perdida ?? o.fecha_hallazgo ?? o.creado_en;
            return (
              <li key={o.id}>
                <Link href={`/admin/${ruta}/ver/?id=${o.id}`} className={estilos.fila}>
                  <Miniatura foto={o.foto} alt={o.descripcion_publica} />
                  <span className={estilos.principal}>
                    <strong>{o.categoria}</strong>
                    <span className="secundario">{o.descripcion_publica}</span>
                  </span>
                  <span className={estilos.meta}>
                    <span>{o.zona ?? "Sin zona"}</span>
                    <span className="secundario" title={fechaLarga(fecha)}>{haceCuanto(fecha)}</span>
                  </span>
                  <Insignia estado={o.estado} tipo={tipo} />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {siguiente && <div><button className="boton boton-borde" onClick={() => void cargar(siguiente)}>Ver más</button></div>}
    </div>
  );
}

function Miniatura({ foto, alt }: { foto: string | null; alt: string }) {
  const sinFoto = <span className={estilos.sinFoto} aria-hidden="true" />;
  if (!foto) return sinFoto;
  return <Foto className={estilos.miniatura} src={urlFoto(foto)} alt={alt} loading="lazy" width={72} height={54} respaldo={sinFoto} />;
}

// ------------------------------------------------------------------ detalle
export function DetalleObjeto({ tipo }: { tipo: Tipo }) {
  const id = useSearchParams().get("id");
  const avisar = useAviso();
  const [obj, setObj] = useState<ObjetoDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nuevas, setNuevas] = useState<File[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [aBorrar, setABorrar] = useState<FotoInfo | null>(null);
  const [borrando, setBorrando] = useState(false);
  const [ampliada, setAmpliada] = useState<FotoInfo | null>(null);
  const ruta = RUTA[tipo];

  const cargar = useCallback(async () => {
    if (!id) return setError("Falta el identificador.");
    try {
      setObj(await api<ObjetoDetalle>(`/${ruta}/${encodeURIComponent(id)}`));
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo cargar.");
    }
  }, [id, ruta]);
  useEffect(() => { void cargar(); }, [cargar]);
  useEffect(() => {
    if (!ampliada) return;
    const cerrar = (e: KeyboardEvent) => e.key === "Escape" && setAmpliada(null);
    window.addEventListener("keydown", cerrar);
    return () => window.removeEventListener("keydown", cerrar);
  }, [ampliada]);

  async function subirNuevas() {
    if (!obj) return;
    setSubiendo(true);
    let ok = 0;
    for (const archivo of nuevas) {
      try { await subirFoto(ruta, obj.id, archivo); ok += 1; }
      catch (e) { avisar("error", e instanceof ErrorApi ? e.message : `No se pudo subir ${archivo.name}.`); }
    }
    if (ok) avisar("ok", ok === 1 ? "Foto agregada" : `${ok} fotos agregadas`);
    setNuevas([]);
    setSubiendo(false);
    await cargar();
  }

  async function borrar() {
    if (!aBorrar) return;
    setBorrando(true);
    try {
      await api(`/fotos/${aBorrar.id}`, { method: "DELETE" });
      avisar("ok", "Foto borrada");
      setABorrar(null);
      await cargar();
    } catch (e) {
      avisar("error", e instanceof ErrorApi ? e.message : "No se pudo borrar la foto.");
    } finally {
      setBorrando(false);
    }
  }

  if (error) return <p className="aviso aviso-error" role="alert">{error}</p>;
  if (!obj) return <div className="esqueleto" style={{ height: "20rem", maxWidth: "46rem" }} aria-busy="true" />;

  const abierto = ABIERTOS.has(obj.estado);
  const cupo = MAX_FOTOS - obj.fotos.length;
  const fecha = obj.fecha_perdida ?? obj.fecha_hallazgo!;

  return (
    <div className={estilos.pagina}>
      <Link href={`/admin/${ruta}/`} className="pequeno">Volver a {tipo === "perdido" ? "reportes" : "hallazgos"}</Link>
      <header className={estilos.cabecera}>
        <div>
          <h1>{obj.categoria}</h1>
          <p className="secundario">{obj.descripcion_publica}</p>
        </div>
        <Insignia estado={obj.estado} tipo={tipo} />
      </header>

      <section className={estilos.bloque} aria-labelledby="fotos-titulo">
        <h2 id="fotos-titulo">Fotos</h2>
        {obj.fotos.length > 0 ? (
          <div className={estilos.galeria}>
            {obj.fotos.map((f) => (
              <figure key={f.id}>
                <button className={estilos.fotoBoton} onClick={() => setAmpliada(f)} aria-label={`Ampliar la foto ${f.orden}`}>
                  <Foto src={urlFoto(f.id)} alt={`Foto ${f.orden} de ${obj.categoria}`}
                    respaldo={<span className="secundario pequeno">Archivo no disponible</span>} />
                </button>
                {abierto && <button className="boton boton-borde boton-chico" onClick={() => setABorrar(f)}>Borrar</button>}
              </figure>
            ))}
          </div>
        ) : <p className="secundario">Sin fotos.</p>}
        {abierto && cupo > 0 && (
          <div className={estilos.agregarFotos}>
            <SubirFotos archivos={nuevas} onCambio={setNuevas} cupo={cupo}
              aviso={tipo === "hallado" ? "Las fotos de lo hallado nunca se publican." : "Las fotos de lo perdido salen en el portal (salvo documentos)."} />
            {nuevas.length > 0 && (
              <div><button className="boton" onClick={() => void subirNuevas()} disabled={subiendo}>
                {subiendo ? "Subiendo…" : nuevas.length === 1 ? "Subir foto" : `Subir ${nuevas.length} fotos`}
              </button></div>
            )}
          </div>
        )}
      </section>

      <section className={estilos.bloque}>
        <h2>Datos</h2>
        <dl className={estilos.datos}>
          <div><dt>Zona</dt><dd>{obj.zona ?? "Sin zona"}</dd></div>
          <div><dt>{tipo === "perdido" ? "Se perdió" : "Se encontró"}</dt><dd>{fechaLarga(fecha)}{obj.hora_aprox ? `, ${obj.hora_aprox.slice(0, 5)} h` : ""}</dd></div>
          <div className={estilos.ancho}><dt>Descripción completa</dt><dd>{obj.descripcion}</dd></div>
          {tipo === "perdido" && <div className={estilos.ancho}><dt>Detalle de control</dt><dd>{obj.detalle_control || "No registrado"}</dd></div>}
          {tipo === "hallado" && <>
            <div><dt>Ubicación en bodega</dt><dd>{obj.ubicacion_bodega || "Sin registrar"}</dd></div>
            <div><dt>Custodia hasta</dt><dd>{obj.vence_en ? fechaLarga(obj.vence_en) : ""}</dd></div>
            {obj.encontrado_por && <div><dt>Lo entregó</dt><dd>{obj.encontrado_por}</dd></div>}
          </>}
        </dl>
      </section>

      {tipo === "perdido" && obj.nombres && (
        <section className={estilos.bloque} aria-labelledby="dueno-titulo">
          <h2 id="dueno-titulo">Dueño</h2>
          <dl className={estilos.datos}>
            <div><dt>Nombre</dt><dd>{obj.nombres} {obj.apellidos}</dd></div>
            <div><dt>Documento</dt><dd>{obj.tipo_documento} {obj.numero_documento}</dd></div>
            <div><dt>Correo</dt><dd>{obj.correo_institucional ?? "Sin correo"}</dd></div>
          </dl>
          <p className="secundario pequeno">Esta consulta de datos personales quedó registrada en la auditoría.</p>
        </section>
      )}

      <Confirmar abierto={!!aBorrar} titulo="¿Borrar esta foto?" accion="Borrar foto" peligro ocupado={borrando}
        onConfirmar={() => void borrar()} onCancelar={() => setABorrar(null)}>
        La foto se elimina del almacenamiento y no se puede recuperar.
      </Confirmar>
      {ampliada && (
        <dialog open className={estilos.visor} onClick={() => setAmpliada(null)} aria-label="Foto ampliada">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={urlFoto(ampliada.id, "grande")} alt={`Foto ${ampliada.orden} ampliada`} />
          <button className="boton boton-chico" onClick={() => setAmpliada(null)} autoFocus>Cerrar</button>
        </dialog>
      )}
    </div>
  );
}
