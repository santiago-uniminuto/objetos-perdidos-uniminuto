"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import type { Par } from "@/componentes/admin/Coincidencias";
import { useAviso } from "@/componentes/ui/Avisos";
import { Campo } from "@/componentes/ui/Basicos";
import { Confirmar } from "@/componentes/ui/Confirmar";
import { Foto } from "@/componentes/ui/Foto";
import { api, ErrorApi, type ObjetoDetalle, urlFoto } from "@/lib/api";

import estilos from "./Entrega.module.css";
import formulario from "./Formulario.module.css";

type Motivo = "documento" | "pregunta_control" | "otro";
const MOTIVOS: { valor: Motivo; nombre: string }[] = [
  { valor: "pregunta_control", nombre: "No respondió bien la pregunta de control" },
  { valor: "documento", nombre: "El documento no coincide o no lo trajo" },
  { valor: "otro", nombre: "Otro motivo (descríbelo en observaciones)" },
];
type Resultado = {
  entregado: boolean; entrega_id?: string; numero_acta?: string; intentos?: number; restantes?: number; liberada?: boolean;
};

/** Entrega al dueño: identidad + pregunta de control + acta. Sin las dos verificaciones no se entrega.
 *  El número del acta lo asigna el sistema al registrar; después se imprime, se firma y se sube firmada. */
export function RegistrarEntrega() {
  const id = useSearchParams().get("coincidencia");
  const avisar = useAviso();
  const [par, setPar] = useState<Par | null>(null);
  const [reporte, setReporte] = useState<ObjetoDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [identidad, setIdentidad] = useState(false);
  const [control, setControl] = useState(false);
  const [verRespuesta, setVerRespuesta] = useState(false);
  const [observaciones, setObservaciones] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [confirmarFallo, setConfirmarFallo] = useState(false);
  const [listo, setListo] = useState<{ id: string; numero: string } | null>(null);
  const [motivo, setMotivo] = useState<Motivo>("pregunta_control");

  useEffect(() => {
    (async () => {
      try {
        const pares = (await api<{ items: Par[] }>("/coincidencias?estado=verificada&limite=200")).items;
        const p = pares.find((x) => x.id === id);
        if (!p) return setError("Esta coincidencia no está pendiente de entrega (puede que ya se haya entregado).");
        if (!p.puede_decidir) return setError(`El objeto está en ${p.sede_custodia}: la entrega se registra allá.`);
        setPar(p);
        // Lectura de datos personales del dueño: la API la deja en la auditoría
        setReporte(await api<ObjetoDetalle>(`/reportes/${p.reporte_id}`));
      } catch (e) {
        setError(e instanceof ErrorApi ? e.message : "No se pudo cargar la entrega.");
      }
    })();
  }, [id]);

  async function enviar(verificacion_ok: boolean) {
    setOcupado(true);
    try {
      // El acta solo existe si se entrega; un intento fallido lleva su motivo (ADR-019)
      const r = await api<Resultado>("/entregas", { method: "POST", json: {
        coincidencia_id: id, verificacion_ok, observaciones: observaciones.trim() || null,
        ...(verificacion_ok ? {} : { motivo_fallo: motivo }),
      } });
      if (r.entregado) setListo({ id: r.entrega_id!, numero: r.numero_acta! });
      else {
        avisar("ok", r.liberada
          ? "Tercer intento fallido: la coincidencia se descartó y el objeto vuelve a custodia, a la espera de su dueño."
          : `Intento ${r.intentos} de 3 registrado. El objeto sigue en custodia.`);
        window.location.assign("/admin/coincidencias/");
      }
    } catch (e) {
      avisar("error", e instanceof ErrorApi ? e.message : "No se pudo registrar la entrega.");
    } finally {
      setOcupado(false);
      setConfirmarFallo(false);
    }
  }

  if (error) return <div className={estilos.pagina}><p className="aviso aviso-error" role="alert">{error}</p><Link href="/admin/coincidencias/">Volver a coincidencias</Link></div>;
  if (!par || !reporte) return <div className="esqueleto" style={{ height: "24rem", maxWidth: "44rem" }} aria-busy="true" />;

  if (listo) {
    return (
      <div className={formulario.exito}>
        <p className={formulario.exitoTitulo} aria-live="polite">
          {["Objeto", "entregado"].map((p, i) => <span key={p} style={{ animationDelay: `${i * 90}ms` }}>{p}</span>)}
        </p>
        <p className={estilos.numeroActa}>{listo.numero}</p>
        <p className="secundario">
          El caso quedó cerrado y el acta quedó numerada. Imprímela, que la firmen quien entrega y quien recibe, y sube
          una foto del acta firmada para dejarla en el registro.
        </p>
        <div className={formulario.acciones}>
          <Link className="boton boton-senal" href={`/admin/entregas/acta/?id=${listo.id}`}>Imprimir y firmar el acta</Link>
          <Link className="boton boton-borde" href="/admin/coincidencias/">Volver a coincidencias</Link>
        </div>
      </div>
    );
  }

  const puedeEntregar = identidad && control;
  return (
    <div className={estilos.pagina}>
      <Link href="/admin/coincidencias/" className="pequeno">Volver a coincidencias</Link>
      <h1>Registrar entrega</h1>
      {par.intentos_fallidos > 0 && (
        <p className="aviso" role="status">
          Ya hubo {par.intentos_fallidos} {par.intentos_fallidos === 1 ? "intento fallido" : "intentos fallidos"} de 3.
          {par.intentos_fallidos === 2 && " Si este también falla, la coincidencia se descarta y el objeto vuelve a custodia."}
        </p>
      )}

      <div className={estilos.objeto}>
        <Foto className={estilos.foto} src={par.hallazgo_fotos[0] ? urlFoto(par.hallazgo_fotos[0]) : undefined}
          alt="" respaldo={<span className={estilos.foto} />} />
        <div>
          <h2>{par.hallazgo_categoria}: {par.hallazgo}</h2>
          <p className="secundario">{par.ubicacion_bodega ? `Está en bodega: ${par.ubicacion_bodega}` : "Sin ubicación en bodega"}</p>
        </div>
      </div>

      <ol className={estilos.verificacion}>
        <li data-hecho={identidad || undefined}>
          <h3>Identidad del dueño</h3>
          <p>Pide el carné o el documento. Debe coincidir con:</p>
          <p className={estilos.dato}>{reporte.nombres} {reporte.apellidos}, {reporte.tipo_documento} {reporte.numero_documento}</p>
          <label className={estilos.check}><input type="checkbox" checked={identidad} onChange={(e) => setIdentidad(e.target.checked)} />
            Mostró su documento y coincide</label>
        </li>
        <li data-hecho={control || undefined}>
          <h3>Pregunta de control</h3>
          {reporte.detalle_control ? <>
            <p>Pregúntale un detalle que solo el dueño sabría. Mira la respuesta esperada después de que conteste.</p>
            {verRespuesta
              ? <p className={estilos.dato}>{reporte.detalle_control}</p>
              : <button className="boton boton-borde boton-chico" onClick={() => setVerRespuesta(true)}>Ver la respuesta esperada</button>}
          </> : <p>No se registró detalle de control. Pídele que describa el objeto con detalle y compáralo con las fotos.</p>}
          <label className={estilos.check}><input type="checkbox" checked={control} onChange={(e) => setControl(e.target.checked)} />
            Respondió correctamente</label>
        </li>
        <li>
          <h3>Acta de entrega</h3>
          <p>
            No tienes que escribir el número: el sistema lo asigna al registrar la entrega (por ejemplo{" "}
            <b>ACTA-BOG-CALLE80-2026-00042</b>) y te deja el acta lista para imprimir y firmar.
          </p>
          <Campo etiqueta="Observaciones (opcional)" ayuda="Salen impresas en el acta. Ej.: se entrega con el forro, falta el cargador.">
            <input value={observaciones} maxLength={500} onChange={(e) => setObservaciones(e.target.value)} />
          </Campo>
        </li>
      </ol>

      <div className={formulario.acciones}>
        <button className="boton boton-senal" disabled={!puedeEntregar || ocupado} onClick={() => void enviar(true)}>
          {ocupado ? "Registrando…" : "Entregar objeto"}
        </button>
        <button className="boton boton-borde" disabled={ocupado} onClick={() => setConfirmarFallo(true)}>No pasó la verificación</button>
      </div>
      {!puedeEntregar && <p className="secundario pequeno">Para entregar, completa las dos verificaciones.</p>}

      <Confirmar abierto={confirmarFallo} titulo="¿No pasó la verificación?" accion={par.intentos_fallidos >= 2 ? "Registrar y liberar" : "Registrar intento"} peligro ocupado={ocupado}
        onConfirmar={() => void enviar(false)} onCancelar={() => setConfirmarFallo(false)}>
        <p>
          Será el intento {par.intentos_fallidos + 1} de 3.{" "}
          {par.intentos_fallidos >= 2
            ? "Es el último: la coincidencia se descartará y el objeto volverá a custodia, a la espera de su dueño."
            : "El objeto no se entrega y sigue en custodia."}
        </p>
        <fieldset className={estilos.motivos}>
          <legend>¿Qué falló?</legend>
          {MOTIVOS.map((m) => (
            <label key={m.valor} className={estilos.check}>
              <input type="radio" name="motivo" value={m.valor} checked={motivo === m.valor} onChange={() => setMotivo(m.valor)} />
              {m.nombre}
            </label>
          ))}
        </fieldset>
      </Confirmar>
    </div>
  );
}
