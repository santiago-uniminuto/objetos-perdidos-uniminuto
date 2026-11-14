"use client";

import { FormularioObjeto } from "@/componentes/admin/FormularioObjeto";

export default function Pagina() {
  return (
    <div style={{ display: "grid", gap: "1.2rem" }}>
      <h1 style={{ fontSize: "clamp(2rem, 4vw, 2.7rem)" }}>Registrar hallazgo</h1>
      <FormularioObjeto tipo="hallado" />
    </div>
  );
}
