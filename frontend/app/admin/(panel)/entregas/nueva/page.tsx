"use client";

import { Suspense } from "react";

import { RegistrarEntrega } from "@/componentes/admin/Entrega";

export default function Pagina() {
  return (
    <Suspense>
      <RegistrarEntrega />
    </Suspense>
  );
}
