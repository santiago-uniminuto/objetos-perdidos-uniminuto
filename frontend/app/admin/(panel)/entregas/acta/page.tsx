"use client";

import { Suspense } from "react";

import { ActaEntrega } from "@/componentes/admin/Actas";

export default function Pagina() {
  return (
    <Suspense>
      <ActaEntrega />
    </Suspense>
  );
}
