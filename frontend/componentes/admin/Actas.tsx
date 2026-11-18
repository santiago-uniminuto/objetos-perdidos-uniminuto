"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAviso } from "@/componentes/ui/Avisos";
import { api, ErrorApi } from "@/lib/api";
import { fechaCorta, fechaLarga } from "@/lib/formato";

import estilos from "./Actas.module.css";

type FilaEntrega = {
  id: string; creado_en: string; numero_acta: string; firmada: boolean; acta_subida_en: string | null;
  categoria: string; descripcion_publica: string; entregado_por: string;
};

type Acta = {
  id: string; numero_acta: string; creado_en: string; metodo_verificacion: string; observaciones: string | null;
  firmada: boolean; acta_subida_en: string | null; acta_subida_por: string | null;
  sede: string; ciudad: string; direccion: string | null; entregado_por: string; correo_admin: string;
  nombres: string; apellidos: string; tipo_documento: string; numero_documento: string; programa: string | null;
  anonimizado: boolean;
  categoria: string; descripcion: string; fecha_hallazgo: string; ubicacion_bodega: string | null;
  zona_hallazgo: string | null; fecha_perdida: string; sede_reporte: string;
};

const hora = (iso: string) =>
  new Date(iso).toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit", timeZone: "America/Bogota" });
const diaBogota = (iso: string) => new Date(iso).toLocaleDateString("en-CA", { timeZone: "America/Bogota" });
const fechaHora = (iso: string) => `${fechaLarga(diaBogota(iso))}, ${hora(iso)}`;

// ------------------------------------------------------------------ registro de entregas
export function RegistroEntregas() {
  const [filtro, setFiltro] = useState<"" | "pendiente" | "firmada">("");
  const [filas, setFilas] = useState<FilaEntrega[] | null>(null);
  const [siguiente, setSiguiente] = useState<string | null>(null);
  const [sinFirma, setSinFirma] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async (cursor?: string) => {
    try {
      const q = new URLSearchParams({ limite: "30", ...(filtro ? { firma: filtro } : {}), ...(cursor ? { cursor } : {}) });
      const r = await api<{ items: FilaEntrega[]; siguiente: string | null; sin_firma: number }>(`/entregas?${q}`);
      setFilas((antes) => (cursor ? [...(antes ?? []), ...r.items] : r.items));
      setSiguiente(r.siguiente);
      setSinFirma(r.sin_firma);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo cargar el registro de entregas.");
    }
  }, [filtro]);

  useEffect(() => {
    setFilas(null);
    void cargar();
  }, [cargar]);

  const pestanas = [
    { valor: "" as const, nombre: "Todas" },
    { valor: "pendiente" as const, nombre: `Sin acta firmada${sinFirma ? ` (${sinFirma})` : ""}` },
    { valor: "firmada" as const, nombre: "Con acta firmada" },
  ];

  return (
    <div className={estilos.pagina}>
      <header>
        <h1>Entregas y actas</h1>
        <p className="secundario">
          Cada entrega tiene un acta numerada por el sistema. Imprímela, fírmenla quien entrega y quien recibe, y sube la foto
          del acta firmada: así queda el soporte en el registro.
        </p>
      </header>
      {sinFirma > 0 && (
        <p className="aviso" role="status">
          Hay {sinFirma} {sinFirma === 1 ? "entrega" : "entregas"} sin la foto del acta firmada.
        </p>
      )}
      <div className={estilos.pestanas} role="group" aria-label="Filtrar entregas">
        {pestanas.map((p) => (
          <button key={p.valor} type="button" aria-pressed={filtro === p.valor} onClick={() => setFiltro(p.valor)}
            className={filtro === p.valor ? estilos.pestanaActiva : estilos.pestana}>
            {p.nombre}
          </button>
        ))}
      </div>
      {error && <p className="aviso aviso-error" role="alert">{error}</p>}
      {filas === null ? (
        <div className="esqueleto" style={{ height: "16rem" }} aria-busy="true" />
      ) : filas.length === 0 ? (
        <p className="secundario">No hay entregas {filtro === "pendiente" ? "pendientes de firma" : filtro === "firmada" ? "con acta firmada" : "registradas"}.</p>
      ) : (
        <div className={estilos.tablaCaja}>
          <table className={estilos.tabla}>
            <thead>
              <tr><th scope="col">Acta</th><th scope="col">Fecha</th><th scope="col">Objeto</th><th scope="col">Entregó</th><th scope="col">Firma</th><th scope="col"><span className="visualmente-oculto">Acción</span></th></tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.id}>
                  <td className={estilos.numero}>{f.numero_acta}</td>
                  <td className={estilos.fecha}>{fechaCorta(diaBogota(f.creado_en))} {diaBogota(f.creado_en).slice(0, 4)} · {hora(f.creado_en)}</td>
                  <td><b>{f.categoria}</b> · {f.descripcion_publica}</td>
                  <td>{f.entregado_por}</td>
                  <td>{f.firmada ? <span className={estilos.firmada}>✓ Firmada</span> : <span className={estilos.pendiente}>Pendiente</span>}</td>
                  <td className={estilos.accion}><Link className="boton boton-borde boton-chico" href={`/admin/entregas/acta/?id=${f.id}`}>{f.firmada ? "Ver acta" : "Imprimir / subir"}</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {siguiente && <button type="button" className="boton boton-borde" onClick={() => void cargar(siguiente)}>Cargar más</button>}
    </div>
  );
}

// ------------------------------------------------------------------ acta para imprimir y firmar
export function ActaEntrega() {
  const id = useSearchParams().get("id");
  const avisar = useAviso();
  const [acta, setActa] = useState<Acta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [version, setVersion] = useState(0);
  const archivo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!id) return setError("Falta el identificador de la entrega.");
    api<Acta>(`/entregas/${id}/acta`).then(setActa).catch((e) => setError(e instanceof ErrorApi ? e.message : "No se pudo cargar el acta."));
  }, [id]);

  async function subir(f: File) {
    setSubiendo(true);
    try {
      const datos = new FormData();
      datos.append("archivo", f);
      const r = await api<{ acta_subida_en: string }>(`/entregas/${id}/acta-firmada`, { method: "POST", body: datos });
      setActa((a) => (a ? { ...a, firmada: true, acta_subida_en: r.acta_subida_en } : a));
      setVersion((v) => v + 1);
      avisar("ok", "Acta firmada guardada en el registro.");
    } catch (e) {
      avisar("error", e instanceof ErrorApi ? e.message : "No se pudo subir el acta firmada.");
    } finally {
      setSubiendo(false);
      if (archivo.current) archivo.current.value = "";
    }
  }

  if (error) return <div className={estilos.pagina}><p className="aviso aviso-error" role="alert">{error}</p><Link href="/admin/entregas/">Volver al registro</Link></div>;
  if (!acta) return <div className="esqueleto" style={{ height: "40rem", maxWidth: "52rem" }} aria-busy="true" />;

  const dueno = acta.anonimizado ? "Datos anonimizados a solicitud del titular" : `${acta.nombres} ${acta.apellidos}`;
  return (
    <div className={estilos.pagina}>
      <div className={estilos.barra}>
        <Link href="/admin/entregas/" className="pequeno">← Registro de entregas</Link>
        <div className={estilos.acciones}>
          <button type="button" className="boton boton-senal" onClick={() => window.print()}>Imprimir acta</button>
          <input ref={archivo} type="file" accept="image/jpeg,image/png,image/webp,image/heic" capture="environment" hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void subir(f); }} />
          <button type="button" className="boton boton-borde" disabled={subiendo} onClick={() => archivo.current?.click()}>
            {subiendo ? "Subiendo…" : acta.firmada ? "Reemplazar acta firmada" : "Subir acta firmada"}
          </button>
        </div>
      </div>

      <section className={estilos.estadoFirma} aria-label="Acta firmada">
        {acta.firmada ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element -- imagen privada servida por la API */}
            <a href={`/api/v1/entregas/${acta.id}/acta-firmada/grande?v=${version}`} target="_blank" rel="noopener noreferrer">
              <img src={`/api/v1/entregas/${acta.id}/acta-firmada/mini?v=${version}`} alt={`Foto del acta firmada ${acta.numero_acta}`} className={estilos.miniatura} />
            </a>
            <div>
              <p><b>✓ Acta firmada en el registro</b></p>
              <p className="secundario pequeno">
                Subida {acta.acta_subida_en ? fechaHora(acta.acta_subida_en) : ""}{acta.acta_subida_por ? ` por ${acta.acta_subida_por}` : ""}. Toca la foto para verla completa.
              </p>
            </div>
          </>
        ) : (
          <p>
            <b>Falta el acta firmada.</b> Imprime esta acta, fírmenla quien entrega y quien recibe, y súbela con una foto
            (con el celular se abre la cámara).
          </p>
        )}
      </section>

      <article className={`${estilos.hoja} acta-imprimible`} aria-label={`Acta de entrega ${acta.numero_acta}`}>
        <header className={estilos.hojaCabeza}>
          <div className={estilos.membrete}>
            <span className={estilos.simbolo} aria-hidden="true" />
            <div>
              <p className={estilos.institucion}>Corporación Universitaria Minuto de Dios · UNIMINUTO</p>
              <p className={estilos.sistema}>Sistema de objetos perdidos y hallados</p>
            </div>
          </div>
          <div className={estilos.numeroCaja}>
            <span>Acta N.º</span>
            <b>{acta.numero_acta}</b>
          </div>
        </header>

        <h2 className={estilos.titulo}>Acta de entrega de objeto hallado</h2>
        <p className={estilos.lugar}>
          {acta.sede}{acta.direccion ? ` · ${acta.direccion}` : ""} · {acta.ciudad} · {fechaHora(acta.creado_en)}
        </p>

        <h3>1. Objeto entregado</h3>
        <dl className={estilos.datos}>
          <dt>Categoría</dt><dd>{acta.categoria}</dd>
          <dt>Descripción</dt><dd>{acta.descripcion}</dd>
          <dt>Hallado</dt><dd>{fechaLarga(acta.fecha_hallazgo)}{acta.zona_hallazgo ? ` · ${acta.zona_hallazgo}` : ""}</dd>
          <dt>Bodega</dt><dd>{acta.ubicacion_bodega ?? "Sin ubicación registrada"}</dd>
          <dt>Reportado perdido</dt><dd>{fechaLarga(acta.fecha_perdida)} · sede {acta.sede_reporte}</dd>
        </dl>

        <h3>2. Persona que recibe (dueño)</h3>
        <dl className={estilos.datos}>
          <dt>Nombre</dt><dd>{dueno}</dd>
          {!acta.anonimizado && <><dt>Documento</dt><dd>{acta.tipo_documento} {acta.numero_documento}</dd></>}
          {acta.programa && !acta.anonimizado && <><dt>Programa</dt><dd>{acta.programa}</dd></>}
        </dl>

        <h3>3. Verificación</h3>
        <ul className={estilos.checks}>
          <li>☑ Presentó documento de identidad o carné y coincide con el reporte.</li>
          <li>☑ Respondió correctamente la pregunta de control sobre el objeto.</li>
        </ul>

        <h3>4. Observaciones</h3>
        <p className={estilos.observaciones}>{acta.observaciones || "Ninguna."}</p>

        <p className={estilos.declaracion}>
          Quien recibe declara que el objeto descrito es de su propiedad y que lo recibe en el estado en que se encuentra,
          a satisfacción. Los datos personales de esta acta se tratan conforme a la Ley 1581 de 2012 y solo se usan para
          soportar esta entrega.
        </p>

        <div className={estilos.firmas}>
          <div>
            <span className={estilos.linea} />
            <p><b>Entrega:</b> {acta.entregado_por}</p>
            <p>Administrador de sede · {acta.sede}</p>
          </div>
          <div>
            <span className={estilos.linea} />
            <p><b>Recibe:</b> {acta.anonimizado ? "" : `${acta.nombres} ${acta.apellidos}`}</p>
            <p>{acta.anonimizado ? "Documento:" : `${acta.tipo_documento} ${acta.numero_documento}`}</p>
          </div>
        </div>

        <footer className={estilos.pie}>
          Acta generada por el sistema · número único e irrepetible en la sede · {acta.numero_acta}
        </footer>
      </article>
    </div>
  );
}
