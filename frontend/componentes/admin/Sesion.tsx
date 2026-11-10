"use client";

import { useRouter } from "next/navigation";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import { api, ErrorApi, type Usuario } from "@/lib/api";

const Contexto = createContext<Usuario | null>(null);

export function useUsuario(): Usuario {
  const u = useContext(Contexto);
  if (!u) throw new Error("useUsuario fuera de <ConSesion>");
  return u;
}

/** Pide /auth/yo: sin sesión (o vencida) manda al login. La cookie la valida la API, no el navegador. */
export function ConSesion({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Usuario>("/auth/yo")
      .then(setUsuario)
      .catch((e) => {
        if (e instanceof ErrorApi && e.estado === 401) router.replace("/admin/login/");
        else setError(e instanceof ErrorApi ? e.message : "No se pudo verificar la sesión.");
      });
  }, [router]);

  if (error) return <p className="aviso aviso-error" style={{ margin: "2rem" }}>{error}</p>;
  if (!usuario) return <p className="secundario" style={{ margin: "2rem" }}>Verificando tu sesión…</p>;
  return <Contexto.Provider value={usuario}>{children}</Contexto.Provider>;
}

export async function cerrarSesion() {
  await api("/auth/logout", { method: "POST" }).catch(() => undefined);
  window.location.assign("/admin/login/");
}
