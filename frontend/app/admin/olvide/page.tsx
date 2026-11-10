"use client";

import Link from "next/link";
import { useState } from "react";

import { Acceso, Formulario } from "@/componentes/admin/Acceso";
import { api, ErrorApi } from "@/lib/api";

export default function Olvide() {
  const [email, setEmail] = useState("");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function pedir() {
    setEnviando(true);
    setError(null);
    try {
      const r = await api<{ mensaje: string }>("/auth/olvide-contrasena", { method: "POST", json: { email } });
      setMensaje(r.mensaje);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo enviar la solicitud.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Acceso titulo="Restablecer contraseña">
      {mensaje ? (
        <>
          <p className="aviso aviso-ok" role="status">
            {mensaje}
          </p>
          <Link href="/admin/login/">Volver al ingreso</Link>
        </>
      ) : (
        <>
          <p className="secundario">
            Escribe tu correo institucional y te enviaremos un enlace para crear una contraseña nueva.
          </p>
          <Formulario onSubmit={pedir}>
            <label className="campo">
              <span>Correo institucional</span>
              <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            {error && (
              <p className="aviso aviso-error" role="alert">
                {error}
              </p>
            )}
            <button className="boton boton-senal" disabled={enviando}>
              {enviando ? "Enviando…" : "Enviar enlace"}
            </button>
          </Formulario>
          <p className="secundario pequeno">
            ¿No te llega el correo? Pide a otra persona del equipo que genere el enlace desde el servidor.
          </p>
          <Link href="/admin/login/" className="pequeno">
            Volver al ingreso
          </Link>
        </>
      )}
    </Acceso>
  );
}
