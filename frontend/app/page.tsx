"use client";

import { useCallback, useEffect, useState } from "react";

import { Encabezado } from "@/componentes/Encabezado";
import { Etiqueta } from "@/componentes/Etiqueta";
import { api, type Catalogos, ErrorApi, type ObjetoPublico, type PaginaPublica } from "@/lib/api";

import estilos from "./portal.module.css";

type Filtros = { sede: string; categoria: string; zona: string; desde: string };
const INICIALES: Filtros = { sede: "1", categoria: "", zona: "", desde: "" };

export default function Portal() {
  const [catalogos, setCatalogos] = useState<Catalogos | null>(null);
  const [filtros, setFiltros] = useState<Filtros>(INICIALES);
  const [items, setItems] = useState<ObjetoPublico[]>([]);
  const [siguiente, setSiguiente] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Catalogos>("/catalogos").then(setCatalogos).catch(() => setCatalogos(null));
  }, []);

  const cargar = useCallback(async (f: Filtros, cursor: string | null) => {
    setCargando(true);
    setError(null);
    const q = new URLSearchParams({ sede: f.sede, limite: "24" });
    if (f.categoria) q.set("categoria", f.categoria);
    if (f.zona) q.set("zona", f.zona);
    if (f.desde) q.set("desde", f.desde);
    if (cursor) q.set("cursor", cursor);
    try {
      const pagina = await api<PaginaPublica>(`/publico/objetos?${q}`);
      setItems((previos) => (cursor ? [...previos, ...pagina.items] : pagina.items));
      setSiguiente(pagina.siguiente);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo cargar la lista.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar(filtros, null);
  }, [filtros, cargar]);

  const cambiar = (campo: keyof Filtros) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) =>
    setFiltros((f) => ({ ...f, [campo]: e.target.value, ...(campo === "sede" ? { zona: "" } : {}) }));

  const zonas = catalogos?.zonas.filter((z) => String(z.sede_id) === filtros.sede) ?? [];
  const hayFiltros = filtros.categoria || filtros.zona || filtros.desde;

  return (
    <>
      <Encabezado />
      <main>
        <section className={estilos.portada}>
          <div className="envoltura">
            <h1 className={estilos.titulo}>Alguien está buscando esto</h1>
            <p className={estilos.bajada}>
              Estos objetos los reportó como perdidos la comunidad UNIMINUTO. Si encontraste uno, llévalo a la oficina
              de objetos perdidos de tu sede: su dueño recibe un aviso por correo.
            </p>
            <a href="#ayuda-titulo" className={estilos.atajo}>
              ¿Perdiste algo? Así lo reportas
            </a>
          </div>
        </section>

        <div className={`envoltura ${estilos.cuerpo}`}>
          <form className={estilos.filtros} onSubmit={(e) => e.preventDefault()} aria-label="Filtrar objetos">
            {catalogos && catalogos.sedes.length > 1 && (
              <label className="campo">
                <span>Sede</span>
                <select value={filtros.sede} onChange={cambiar("sede")}>
                  {catalogos.sedes.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nombre}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="campo">
              <span>Qué es</span>
              <select value={filtros.categoria} onChange={cambiar("categoria")}>
                <option value="">Todas las categorías</option>
                {catalogos?.categorias.map((c) => (
                  <option key={c.id} value={c.codigo}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label className="campo">
              <span>Dónde se perdió</span>
              <select value={filtros.zona} onChange={cambiar("zona")}>
                <option value="">Toda la sede</option>
                {zonas.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label className="campo">
              <span>Perdido desde</span>
              <input type="date" value={filtros.desde} onChange={cambiar("desde")} />
            </label>
            {hayFiltros && (
              <button type="button" className="boton boton-borde" onClick={() => setFiltros((f) => ({ ...INICIALES, sede: f.sede }))}>
                Quitar filtros
              </button>
            )}
          </form>

          {error && (
            <p className="aviso aviso-error" role="alert">
              {error}
            </p>
          )}

          {!error && !cargando && items.length === 0 && (
            <div className={estilos.vacio}>
              <h2>No hay objetos con esos filtros</h2>
              <p className="secundario">
                Prueba con otra categoría o zona. Si perdiste algo y no aparece aquí, repórtalo en la oficina con tu carné.
              </p>
            </div>
          )}

          <ul className={estilos.rejilla} aria-busy={cargando}>
            {items.map((o) => (
              <li key={o.id}>
                <Etiqueta objeto={o} />
              </li>
            ))}
          </ul>

          {siguiente && (
            <div className={estilos.mas}>
              <button className="boton boton-borde" disabled={cargando} onClick={() => void cargar(filtros, siguiente)}>
                {cargando ? "Cargando…" : "Ver más objetos"}
              </button>
            </div>
          )}

          <aside className={estilos.ayuda} aria-labelledby="ayuda-titulo">
            <h2 id="ayuda-titulo">¿Perdiste algo?</h2>
            <p>
              Acércate a la oficina de objetos perdidos de tu sede con tu carné y repórtalo. Cuando alguien entregue algo
              parecido, te escribimos al correo institucional. Para devolverlo te haremos una pregunta que solo el
              dueño puede responder.
            </p>
            <p className="secundario pequeno">
              Por seguridad no publicamos los objetos encontrados: así evitamos que alguien reclame lo que no es suyo.
            </p>
          </aside>
        </div>
      </main>
    </>
  );
}
