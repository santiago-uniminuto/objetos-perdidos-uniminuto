"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { MarcoPublico } from "@/componentes/Encabezado";
import { Etiqueta } from "@/componentes/Etiqueta";
import { Foto } from "@/componentes/ui/Foto";
import { api, ErrorApi, type ObjetoPublico, urlFoto } from "@/lib/api";

import estilos from "../portal.module.css";

type Detalle = ObjetoPublico & { instrucciones: string };

/** Pasos para quien lo encontró; el segundo usa las instrucciones de la sede que manda la API. */
function pasos(instrucciones: string) {
  return [
    {
      titulo: "Guárdalo con cuidado",
      texto: "No se lo entregues a nadie que diga ser el dueño: la verificación la hace la oficina.",
      icono: <path d="M12 3 5 6v5c0 4.4 3 8.3 7 9.5 4-1.2 7-5.1 7-9.5V6l-7-3Z" />,
    },
    {
      titulo: "Llévalo a la oficina",
      texto: instrucciones || "Llévalo a la oficina de objetos perdidos de tu sede.",
      icono: (
        <>
          <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z" />
          <circle cx="12" cy="10" r="2.4" />
        </>
      ),
    },
    {
      titulo: "Lo registran",
      texto: "El personal lo recibe y el sistema lo compara con este reporte y otros parecidos.",
      icono: (
        <>
          <rect x="5" y="4" width="14" height="17" rx="2" />
          <path d="M9 4.5V3h6v1.5M8.5 11h7M8.5 15h4.5" />
        </>
      ),
    },
    {
      titulo: "Vuelve a su dueño",
      texto: "El dueño recibe un aviso en su correo y lo recoge después de verificar su identidad.",
      icono: (
        <>
          <rect x="3" y="5.5" width="18" height="13" rx="2.2" />
          <path d="m4 7.5 8 5.5 8-5.5" />
        </>
      ),
    },
  ];
}

function SinFoto({ categoria }: { categoria: string }) {
  return (
    <div className={estilos.sinFoto}>
      <svg viewBox="0 0 124 74" aria-hidden="true">
        <path d="M22 2h100v70H22L2 52V22Z" />
        <circle cx="15" cy="37" r="5" />
        <path d="M32 6v62" strokeDasharray="3 4" />
      </svg>
      <strong>{categoria}</strong>
      <span>Este reporte no tiene foto: guíate por la descripción.</span>
    </div>
  );
}

function Contenido() {
  const id = useSearchParams().get("id");
  const [objeto, setObjeto] = useState<Detalle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError("Falta el identificador del objeto.");
      return;
    }
    api<Detalle>(`/publico/objetos/${encodeURIComponent(id)}`)
      .then(setObjeto)
      .catch((e) =>
        setError(e instanceof ErrorApi && e.estado === 404
          ? "Este objeto ya no está publicado: puede que ya lo hayan devuelto a su dueño."
          : e instanceof ErrorApi ? e.message : "No se pudo cargar el objeto."),
      );
  }, [id]);

  const foto = objeto?.fotos?.[0];

  return (
    <div className={estilos.detalle}>
      <Link href="/" className={estilos.volver}>
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <path d="M16 10H4m0 0 5-5m-5 5 5 5" />
        </svg>
        Volver a la lista
      </Link>

      {error && <p className={`aviso aviso-error ${estilos.error}`} role="alert">{error}</p>}

      {!objeto && !error && (
        <div className={estilos.detalleFila} aria-hidden="true">
          <div className={`${estilos.esqueleto} ${estilos.visor}`} />
          <div className={estilos.esqueleto} />
        </div>
      )}

      {objeto && (
        <>
          <div className={estilos.detalleFila}>
            <figure className={estilos.visor}>
              {foto ? (
                <>
                  {/* la misma foto, desenfocada, rellena los lados: nada de franjas blancas */}
                  <Foto className={estilos.visorFondo} src={urlFoto(foto, "grande", true)} alt="" aria-hidden="true" />
                  <Foto className={estilos.visorFoto} src={urlFoto(foto, "grande", true)}
                    alt={`Foto de referencia: ${objeto.descripcion}`} respaldo={<SinFoto categoria={objeto.categoria} />} />
                </>
              ) : (
                <SinFoto categoria={objeto.categoria} />
              )}
            </figure>

            <div className={estilos.detalleInfo}>
              <p className={estilos.antetitulo}>
                <span className={estilos.punto} aria-hidden="true" />
                Reportado como perdido
              </p>
              <Etiqueta objeto={objeto} enlace={false} foto={false} />
              <div className={estilos.tuyo}>
                <span className={estilos.caminoIcono} aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <circle cx="12" cy="8.5" r="3.6" />
                    <path d="M5 20c1-3.6 3.8-5.6 7-5.6s6 2 7 5.6" />
                  </svg>
                </span>
                <div>
                  <strong>¿Es tuyo?</strong>
                  <p>
                    Te avisaremos al correo institucional cuando alguien lo entregue. Para recogerlo lleva tu carné: te
                    harán una pregunta que solo el dueño sabe responder.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <section className={estilos.flujo} aria-labelledby="flujo-titulo">
            <p className={estilos.antetitulo}>¿Lo encontraste?</p>
            <h2 id="flujo-titulo">Así lo devuelves en 4 pasos</h2>
            <ol className={estilos.pasosFlujo}>
              {pasos(objeto.instrucciones).map((p, i) => (
                <li key={p.titulo} style={{ "--i": i } as React.CSSProperties}>
                  <span className={estilos.pasoIcono} aria-hidden="true">
                    <svg viewBox="0 0 24 24">{p.icono}</svg>
                    <span className={estilos.pasoNumero}>{i + 1}</span>
                  </span>
                  <strong>{p.titulo}</strong>
                  <p>{p.texto}</p>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}

export default function PaginaObjeto() {
  return (
    <MarcoPublico>
      <main>
        <Suspense>
          <Contenido />
        </Suspense>
      </main>
    </MarcoPublico>
  );
}
