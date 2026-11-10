"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cerrarSesion, ConSesion, useUsuario } from "@/componentes/admin/Sesion";

import estilos from "./panel.module.css";

const SECCIONES = [
  { href: "/admin/", nombre: "Analítica", roles: ["admin_sede", "auditor"] },
  { href: "/admin/cuenta/", nombre: "Mi cuenta", roles: ["admin_sede", "auditor"] },
] as const;

function Marco({ children }: { children: ReactNode }) {
  const usuario = useUsuario();
  const ruta = usePathname().replace(/\/?$/, "/"); // en desarrollo llega sin la barra final
  return (
    <div className={estilos.marco}>
      <nav className={estilos.lateral} aria-label="Panel">
        <Link href="/" className={estilos.marca}>
          Objetos perdidos
        </Link>
        <ul>
          {SECCIONES.filter((s) => (s.roles as readonly string[]).includes(usuario.rol)).map((s) => (
            <li key={s.href}>
              <Link href={s.href} aria-current={ruta === s.href ? "page" : undefined}>
                {s.nombre}
              </Link>
            </li>
          ))}
        </ul>
        <div className={estilos.usuario}>
          <p>{usuario.nombre}</p>
          <p className={estilos.rol}>{usuario.rol === "auditor" ? "Auditor" : `Admin de la sede ${usuario.sede_id}`}</p>
          <button className={estilos.salir} onClick={() => void cerrarSesion()}>
            Cerrar sesión
          </button>
        </div>
      </nav>
      <main className={estilos.contenido}>{children}</main>
    </div>
  );
}

export default function PanelLayout({ children }: { children: ReactNode }) {
  return (
    <ConSesion>
      <Marco>{children}</Marco>
    </ConSesion>
  );
}
