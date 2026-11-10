"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Acceso, Formulario } from "@/componentes/admin/Acceso";
import { api, ErrorApi, type Usuario } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function entrar() {
    setEnviando(true);
    setError(null);
    try {
      await api<{ usuario: Usuario }>("/auth/login", { method: "POST", json: { email, contrasena } });
      router.replace("/admin/");
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 422) setError("Escribe un correo válido y tu contraseña.");
      else setError(e instanceof ErrorApi ? e.message : "No se pudo iniciar sesión.");
      setContrasena("");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Acceso titulo="Ingreso del personal">
      <p className="secundario">Para administradores de sede y auditores. Usa tu correo institucional.</p>
      <Formulario onSubmit={entrar}>
        <label className="campo">
          <span>Correo institucional</span>
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="campo">
          <span>Contraseña</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
          />
        </label>
        {error && (
          <p className="aviso aviso-error" role="alert">
            {error}
          </p>
        )}
        <button className="boton boton-senal" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </Formulario>
      <Link href="/admin/olvide/" className="pequeno">
        Olvidé mi contraseña
      </Link>
    </Acceso>
  );
}
