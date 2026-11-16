"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { MarcoPublico } from "@/componentes/Encabezado";
import { Etiqueta } from "@/componentes/Etiqueta";
import { api, ErrorApi, type ObjetoPublico } from "@/lib/api";

import estilos from "../portal.module.css";

function Detalle() {
  const id = useSearchParams().get("id");
  const [objeto, setObjeto] = useState<(ObjetoPublico & { instrucciones: string }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError("Falta el identificador del objeto.");
      return;
    }
    api<ObjetoPublico & { instrucciones: string }>(`/publico/objetos/${encodeURIComponent(id)}`)
      .then(setObjeto)
      .catch((e) =>
        setError(e instanceof ErrorApi && e.estado === 404
          ? "Este objeto ya no está publicado: puede que ya lo hayan devuelto a su dueño."
          : e instanceof ErrorApi ? e.message : "No se pudo cargar el objeto."),
      );
  }, [id]);

  return (
    <div className={estilos.detalle}>
      <Link href="/" className={estilos.volver}>
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <path d="M16 10H4m0 0 5-5m-5 5 5 5" />
        </svg>
        Volver a la lista
      </Link>
      {error && <p className={`aviso aviso-error ${estilos.error}`} role="alert">{error}</p>}
      {!objeto && !error && <div className={estilos.esqueleto} aria-hidden="true" />}
      {objeto && (
        <>
          <Etiqueta objeto={objeto} enlace={false} />
          <div className={estilos.instrucciones}>
            <span className={estilos.caminoIcono} aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M12 3v12m0 0-4.5-4.5M12 15l4.5-4.5M4 17v2.5h16V17" />
              </svg>
            </span>
            <div>
              <strong>¿Lo encontraste?</strong>
              <p>{objeto.instrucciones}</p>
            </div>
          </div>
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
          <Detalle />
        </Suspense>
      </main>
    </MarcoPublico>
  );
}
