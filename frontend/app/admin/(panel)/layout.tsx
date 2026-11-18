"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cerrarSesion, ConSesion, useUsuario } from "@/componentes/admin/Sesion";
import { ConAvisos } from "@/componentes/ui/Avisos";

import estilos from "./panel.module.css";

const ICONOS = {
  analitica: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  reportes: (
    <>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="m15 15 5.5 5.5" />
    </>
  ),
  hallazgos: (
    <>
      <path d="M3.5 8.5 12 4l8.5 4.5v9L12 22l-8.5-4.5Z" />
      <path d="m3.5 8.5 8.5 4.5 8.5-4.5M12 13v9" />
    </>
  ),
  coincidencias: (
    <>
      <path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2" />
      <path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2" />
    </>
  ),
  entregas: (
    <>
      <path d="M7 3h8l4 4v14H7Z" />
      <path d="M15 3v4h4M10 12h6M10 16h4" />
    </>
  ),
  auditoria: <path d="M12 3 5 6v5c0 4.4 3 8.3 7 9.5 4-1.2 7-5.1 7-9.5V6l-7-3Zm-3 9 2.2 2.2L15.5 10" />,
  cuenta: (
    <>
      <circle cx="12" cy="8.5" r="3.8" />
      <path d="M4.5 20.5c1.2-4 4.2-6 7.5-6s6.3 2 7.5 6" />
    </>
  ),
};

const SECCIONES = [
  { href: "/admin/", nombre: "Analítica", icono: ICONOS.analitica, roles: ["admin_sede", "auditor"] },
  { href: "/admin/reportes/", nombre: "Reportes de pérdida", icono: ICONOS.reportes, roles: ["admin_sede"] },
  { href: "/admin/hallazgos/", nombre: "Hallazgos", icono: ICONOS.hallazgos, roles: ["admin_sede"] },
  { href: "/admin/coincidencias/", nombre: "Coincidencias", icono: ICONOS.coincidencias, roles: ["admin_sede"] },
  { href: "/admin/entregas/", nombre: "Entregas y actas", icono: ICONOS.entregas, roles: ["admin_sede"] },
  { href: "/admin/auditoria/", nombre: "Auditoría", icono: ICONOS.auditoria, roles: ["auditor"] },
  { href: "/admin/cuenta/", nombre: "Mi cuenta", icono: ICONOS.cuenta, roles: ["admin_sede", "auditor"] },
] as const;

/** Registrar una entrega se abre desde Coincidencias: esa página marca Coincidencias, no Entregas. */
function activa(href: string, ruta: string): boolean {
  if (href === "/admin/") return ruta === href;
  const nueva = ruta.startsWith("/admin/entregas/nueva/");
  if (href === "/admin/coincidencias/") return ruta.startsWith(href) || nueva;
  if (href === "/admin/entregas/") return ruta.startsWith(href) && !nueva;
  return ruta.startsWith(href);
}

const iniciales = (nombre: string) =>
  nombre.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");

function Marco({ children }: { children: ReactNode }) {
  const usuario = useUsuario();
  const ruta = usePathname().replace(/\/?$/, "/"); // en desarrollo llega sin la barra final
  return (
    <div className={estilos.marco}>
      <div className={estilos.decoracion} aria-hidden="true">
        <span className={estilos.rejilla} />
        <span className={estilos.halo} />
      </div>
      <nav className={estilos.lateral} aria-label="Panel">
        <Link href="/" className={estilos.marca}>
          <span className={estilos.simbolo} aria-hidden="true" />
          <span>
            Objetos perdidos
            <small>Panel del personal</small>
          </span>
        </Link>
        <ul>
          {SECCIONES.filter((s) => (s.roles as readonly string[]).includes(usuario.rol)).map((s) => (
            <li key={s.href}>
              <Link href={s.href}
                aria-current={activa(s.href, ruta) ? "page" : undefined}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  {s.icono}
                </svg>
                {s.nombre}
              </Link>
            </li>
          ))}
        </ul>
        <div className={estilos.usuario}>
          <span className={estilos.avatar} aria-hidden="true">
            {iniciales(usuario.nombre)}
          </span>
          <div className={estilos.usuarioTexto}>
            <p className={estilos.nombre}>{usuario.nombre}</p>
            <p className={estilos.rol}>
              {usuario.rol === "auditor" ? "Auditor · todas las sedes" : `Admin · ${usuario.sede ?? `sede ${usuario.sede_id}`}`}
            </p>
          </div>
          <button className={estilos.salir} onClick={() => void cerrarSesion()} aria-label="Cerrar sesión" title="Cerrar sesión">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l4-4-4-4M14 12H4" />
            </svg>
            <span>Salir</span>
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
      <ConAvisos>
        <Marco>{children}</Marco>
      </ConAvisos>
    </ConSesion>
  );
}
