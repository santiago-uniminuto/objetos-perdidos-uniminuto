"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Encabezado } from "@/componentes/Encabezado";
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
    <div className={`envoltura ${estilos.cuerpo}`} style={{ paddingTop: "2rem", maxWidth: "40rem" }}>
      <Link href="/">Volver a la lista</Link>
      {error && <p className="aviso aviso-error" role="alert">{error}</p>}
      {objeto && (
        <>
          <Etiqueta objeto={objeto} enlace={false} />
          <p>{objeto.instrucciones}</p>
        </>
      )}
    </div>
  );
}

export default function PaginaObjeto() {
  return (
    <>
      <Encabezado />
      <main>
        <Suspense>
          <Detalle />
        </Suspense>
      </main>
    </>
  );
}
