"use client";

import { useState } from "react";

import { useUsuario } from "@/componentes/admin/Sesion";
import { api, ErrorApi } from "@/lib/api";

const MINIMO = 12;

export default function Cuenta() {
  const usuario = useUsuario();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function cambiar() {
    if (nueva.length < MINIMO) return setAviso({ tipo: "error", texto: `La contraseña nueva debe tener al menos ${MINIMO} caracteres.` });
    if (nueva !== repetida) return setAviso({ tipo: "error", texto: "Las dos contraseñas nuevas no coinciden." });
    setEnviando(true);
    setAviso(null);
    try {
      await api("/auth/cambiar-contrasena", { method: "POST", json: { actual, nueva } });
      setAviso({ tipo: "ok", texto: "Contraseña actualizada." });
      setActual("");
      setNueva("");
      setRepetida("");
    } catch (e) {
      setAviso({ tipo: "error", texto: e instanceof ErrorApi ? e.message : "No se pudo cambiar la contraseña." });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: "1.4rem", maxWidth: "28rem" }}>
      <h1 style={{ fontSize: "2.4rem" }}>Mi cuenta</h1>
      <p className="secundario">
        {usuario.nombre}, {usuario.rol === "auditor" ? "auditor" : `administrador de la sede ${usuario.sede_id}`}.
      </p>
      <form
        style={{ display: "grid", gap: "1rem" }}
        onSubmit={(e) => {
          e.preventDefault();
          void cambiar();
        }}
      >
        <h2>Cambiar contraseña</h2>
        <label className="campo">
          <span>Contraseña actual</span>
          <input type="password" autoComplete="current-password" required value={actual} onChange={(e) => setActual(e.target.value)} />
        </label>
        <label className="campo">
          <span>Contraseña nueva</span>
          <input type="password" autoComplete="new-password" required minLength={MINIMO} value={nueva} onChange={(e) => setNueva(e.target.value)} />
        </label>
        <label className="campo">
          <span>Repite la contraseña nueva</span>
          <input type="password" autoComplete="new-password" required value={repetida} onChange={(e) => setRepetida(e.target.value)} />
        </label>
        {aviso && (
          <p className={`aviso aviso-${aviso.tipo}`} role={aviso.tipo === "error" ? "alert" : "status"}>
            {aviso.texto}
          </p>
        )}
        <button className="boton" disabled={enviando}>
          {enviando ? "Guardando…" : "Cambiar contraseña"}
        </button>
      </form>
    </div>
  );
}
