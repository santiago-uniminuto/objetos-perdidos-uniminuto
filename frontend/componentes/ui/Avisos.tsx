"use client";

import { createContext, type ReactNode, useCallback, useContext, useState } from "react";

import estilos from "./ui.module.css";

type Aviso = { id: number; tipo: "ok" | "error"; texto: string; saliendo?: boolean };
type Avisar = (tipo: Aviso["tipo"], texto: string) => void;

const Contexto = createContext<Avisar>(() => undefined);

export const useAviso = () => useContext(Contexto);

/** Notificaciones breves (toasts): entran y salen por el mismo lado, se van solas a los 5 s. */
export function ConAvisos({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);

  const quitar = useCallback((id: number) => {
    setAvisos((a) => a.map((x) => (x.id === id ? { ...x, saliendo: true } : x)));
    setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), 200);
  }, []);

  const avisar = useCallback<Avisar>((tipo, texto) => {
    const id = Date.now() + Math.random();
    setAvisos((a) => [...a.slice(-2), { id, tipo, texto }]);
    setTimeout(() => quitar(id), tipo === "error" ? 8000 : 5000);
  }, [quitar]);

  return (
    <Contexto.Provider value={avisar}>
      {children}
      <div className={estilos.avisos} role="status" aria-live="polite">
        {avisos.map((a) => (
          <div key={a.id} className={`${estilos.aviso} ${a.tipo === "error" ? estilos.avisoError : ""}`}
            data-saliendo={a.saliendo || undefined}>
            <span>{a.texto}</span>
            <button onClick={() => quitar(a.id)} aria-label="Cerrar aviso">×</button>
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}
