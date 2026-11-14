"use client";

import { Suspense } from "react";

import { DetalleObjeto } from "@/componentes/admin/Objetos";

export default function Pagina() {
  return (
    <Suspense>
      <DetalleObjeto tipo="hallado" />
    </Suspense>
  );
}
