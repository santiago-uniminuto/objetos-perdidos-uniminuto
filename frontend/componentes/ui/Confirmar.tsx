"use client";

import { type ReactNode, useEffect, useRef } from "react";

import estilos from "./ui.module.css";

/** Confirmación de acciones que no se pueden deshacer. Usa <dialog> nativo: foco atrapado y Esc gratis. */
export function Confirmar({ abierto, titulo, children, accion, peligro = false, ocupado = false, onConfirmar, onCancelar }: {
  abierto: boolean;
  titulo: string;
  children: ReactNode;
  accion: string;
  peligro?: boolean;
  ocupado?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);

  return (
    <dialog ref={ref} className={estilos.dialogo} onCancel={(e) => { e.preventDefault(); onCancelar(); }}
      aria-labelledby="confirmar-titulo">
      <h2 id="confirmar-titulo">{titulo}</h2>
      <div className={estilos.dialogoTexto}>{children}</div>
      <div className={estilos.dialogoAcciones}>
        <button className="boton boton-borde" onClick={onCancelar} disabled={ocupado}>Cancelar</button>
        <button className={`boton ${peligro ? "boton-peligro" : ""}`} onClick={onConfirmar} disabled={ocupado}>
          {ocupado ? "Un momento…" : accion}
        </button>
      </div>
    </dialog>
  );
}
