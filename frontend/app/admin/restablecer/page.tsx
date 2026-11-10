"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Acceso, Formulario } from "@/componentes/admin/Acceso";
import { api, ErrorApi } from "@/lib/api";

const MINIMO = 12;

function FormularioNueva() {
  const token = useSearchParams().get("token") ?? "";
  const [contrasena, setContrasena] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [listo, setListo] = useState(false);
  const [enviando, setEnviando] = useState(false);

  async function guardar() {
    if (contrasena.length < MINIMO) return setError(`La contraseña debe tener al menos ${MINIMO} caracteres.`);
    if (contrasena !== repetida) return setError("Las dos contraseñas no coinciden.");
    setEnviando(true);
    setError(null);
    try {
      await api("/auth/restablecer-contrasena", { method: "POST", json: { token, contrasena } });
      setListo(true);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo guardar la contraseña.");
    } finally {
      setEnviando(false);
    }
  }

  if (!token) {
    return (
      <>
        <p className="aviso aviso-error">Este enlace está incompleto. Ábrelo desde el correo o pide uno nuevo.</p>
        <Link href="/admin/olvide/">Pedir un enlace nuevo</Link>
      </>
    );
  }
  if (listo) {
    return (
      <>
        <p className="aviso aviso-ok" role="status">
          Contraseña actualizada. Ya puedes ingresar con ella.
        </p>
        <Link className="boton boton-senal" href="/admin/login/">
          Ir al ingreso
        </Link>
      </>
    );
  }
  return (
    <Formulario onSubmit={guardar}>
      <label className="campo">
        <span>Contraseña nueva</span>
        <input type="password" autoComplete="new-password" required minLength={MINIMO} value={contrasena}
          onChange={(e) => setContrasena(e.target.value)} aria-describedby="regla" />
      </label>
      <p id="regla" className="secundario pequeno">
        Mínimo {MINIMO} caracteres. Una frase de varias palabras es fácil de recordar y difícil de adivinar.
      </p>
      <label className="campo">
        <span>Repite la contraseña</span>
        <input type="password" autoComplete="new-password" required value={repetida} onChange={(e) => setRepetida(e.target.value)} />
      </label>
      {error && (
        <p className="aviso aviso-error" role="alert">
          {error}
        </p>
      )}
      <button className="boton boton-senal" disabled={enviando}>
        {enviando ? "Guardando…" : "Guardar contraseña"}
      </button>
      {error?.includes("enlace") && <Link href="/admin/olvide/">Pedir un enlace nuevo</Link>}
    </Formulario>
  );
}

export default function Restablecer() {
  return (
    <Acceso titulo="Contraseña nueva">
      <Suspense>
        <FormularioNueva />
      </Suspense>
    </Acceso>
  );
}
