"use client";

import { useCallback, useEffect, useState } from "react";

import { MarcoPublico } from "@/componentes/Encabezado";
import { Etiqueta } from "@/componentes/Etiqueta";
import { api, type Catalogos, ErrorApi, sedesPorRegion, type ObjetoPublico, type PaginaPublica } from "@/lib/api";

import estilos from "./portal.module.css";

type Filtros = { sede: string; categoria: string; zona: string; desde: string };
const INICIALES: Filtros = { sede: "1", categoria: "", zona: "", desde: "" };

const ENCONTRASTE = [
  "Llévalo a la oficina de objetos perdidos de tu sede.",
  "Lo registran y el sistema lo compara con los reportes de la ciudad.",
  "Si coincide, su dueño recibe un aviso en el correo institucional.",
];
const PERDISTE = [
  "Acércate a la oficina de tu sede con tu carné y repórtalo.",
  "Tu reporte aparece en esta lista, sin tus datos personales.",
  "Para devolvértelo te harán una pregunta que solo el dueño sabe.",
];

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
  const elegirCategoria = (codigo: string) => setFiltros((f) => ({ ...f, categoria: codigo }));

  const zonas = catalogos?.zonas.filter((z) => String(z.sede_id) === filtros.sede) ?? [];
  const sede = catalogos?.sedes.find((s) => String(s.id) === filtros.sede);
  const hayFiltros = filtros.categoria || filtros.zona || filtros.desde;
  const primeraCarga = cargando && items.length === 0;

  return (
    <MarcoPublico>
      <main>
        {/* ---------------------------------------------------------------- portada */}
        <section className={estilos.portada}>
          <div className={`envoltura ${estilos.portadaFila}`}>
            <div className={estilos.portadaTexto}>
              <p className={estilos.antetitulo}>
                <span className={estilos.punto} aria-hidden="true" />
                Comunidad UNIMINUTO
              </p>
              <h1 className={estilos.titulo}>
                Alguien está <span className={estilos.resalte}>buscando</span> esto
              </h1>
              <p className={estilos.bajada}>
                Estos objetos los reportó como perdidos la comunidad. Si encontraste uno, llévalo a la oficina de objetos
                perdidos de tu sede: su dueño recibe un aviso por correo.
              </p>
              <div className={estilos.acciones}>
                <a href="#objetos" className="boton boton-senal">
                  Ver objetos perdidos
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path d="M10 4v12m0 0-5-5m5 5 5-5" />
                  </svg>
                </a>
                <a href="#ayuda" className={`boton ${estilos.botonVidrio}`}>
                  ¿Perdiste algo?
                </a>
              </div>
              <ul className={estilos.garantias}>
                <li>
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path d="M10 2.5 4 5v4.5c0 3.8 2.6 6.9 6 8 3.4-1.1 6-4.2 6-8V5l-6-2.5Z" />
                  </svg>
                  Sin datos personales
                </li>
                <li>
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <rect x="2.5" y="4.5" width="15" height="11" rx="2" />
                    <path d="m3.5 6 6.5 5 6.5-5" />
                  </svg>
                  Aviso al correo institucional
                </li>
                <li>
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path d="m5 10.5 3.2 3.2L15 6.8" />
                  </svg>
                  Entrega con verificación
                </li>
              </ul>
            </div>

            {/* escena decorativa: etiquetas colgadas y el aviso que le llega al dueño */}
            <div className={estilos.escena} aria-hidden="true">
              <span className={estilos.cordelEscena} />
              <div className={`${estilos.mini} ${estilos.mini1}`}>
                <span className={estilos.miniOjal} />
                <div>
                  <strong>Audífonos negros</strong>
                  <span>Bloque A · hoy</span>
                </div>
              </div>
              <div className={`${estilos.mini} ${estilos.mini2}`}>
                <span className={estilos.miniOjal} />
                <div>
                  <strong>Termo verde</strong>
                  <span>Biblioteca · ayer</span>
                </div>
              </div>
              <div className={`${estilos.mini} ${estilos.mini3}`}>
                <span className={estilos.miniOjal} />
                <div>
                  <strong>Cuaderno argollado</strong>
                  <span>Cafetería · hace 3 días</span>
                </div>
              </div>
              <div className={estilos.aviso}>
                <span className={estilos.avisoIcono}>
                  <svg viewBox="0 0 20 20">
                    <rect x="2.5" y="4.5" width="15" height="11" rx="2" />
                    <path d="m3.5 6 6.5 5 6.5-5" />
                  </svg>
                </span>
                <div>
                  <strong>¡Apareció algo parecido!</strong>
                  <span>Pasa por la oficina de tu sede</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- lista */}
        <section id="objetos" className={estilos.listado} aria-labelledby="objetos-titulo">
          <div className="envoltura">
            <div className={estilos.barra}>
              <div className={estilos.barraCabeza}>
                <div>
                  <h2 id="objetos-titulo">Objetos que buscan dueño</h2>
                  <p className={estilos.contexto} aria-live="polite">
                    {primeraCarga
                      ? "Cargando…"
                      : `${items.length}${siguiente ? "+" : ""} ${items.length === 1 ? "objeto" : "objetos"}${sede ? ` en ${sede.nombre}` : ""}`}
                  </p>
                </div>
                {hayFiltros && (
                  <button type="button" className={estilos.limpiar}
                    onClick={() => setFiltros((f) => ({ ...INICIALES, sede: f.sede }))}>
                    Quitar filtros ✕
                  </button>
                )}
              </div>

              <form className={estilos.filtros} onSubmit={(e) => e.preventDefault()} aria-label="Filtrar objetos">
                {catalogos && catalogos.sedes.length > 1 && (
                  <label className="campo">
                    <span>Sede</span>
                    <select value={filtros.sede} onChange={cambiar("sede")}>
                      {sedesPorRegion(catalogos.sedes).map(([region, lista]) => (
                        <optgroup key={region} label={region}>
                          {lista.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.nombre}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </label>
                )}
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
              </form>

              {catalogos && (
                <div className={estilos.chips} role="group" aria-label="Qué es">
                  <button type="button" aria-pressed={!filtros.categoria} onClick={() => elegirCategoria("")}>
                    Todo
                  </button>
                  {catalogos.categorias.map((c) => (
                    <button key={c.id} type="button" aria-pressed={filtros.categoria === c.codigo}
                      onClick={() => elegirCategoria(c.codigo)}>
                      {c.nombre}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {error && (
              <p className={`aviso aviso-error ${estilos.error}`} role="alert">
                {error}
              </p>
            )}

            {!error && !cargando && items.length === 0 && (
              <div className={estilos.vacio}>
                <svg viewBox="0 0 64 64" aria-hidden="true">
                  <circle cx="28" cy="28" r="15" />
                  <path d="m39 39 12 12" />
                  <path d="M22 28h12" />
                </svg>
                <h3>No hay objetos con esos filtros</h3>
                <p>Prueba con otra categoría o zona. Si perdiste algo y no aparece, repórtalo en la oficina con tu carné.</p>
              </div>
            )}

            <ul className={estilos.rejilla} aria-busy={cargando}>
              {primeraCarga &&
                Array.from({ length: 6 }, (_, i) => <li key={`e${i}`} className={estilos.esqueleto} aria-hidden="true" />)}
              {items.map((o, i) => (
                <li key={o.id} className={estilos.item} style={{ "--i": i % 12 } as React.CSSProperties}>
                  <Etiqueta objeto={o} />
                </li>
              ))}
            </ul>

            {siguiente && (
              <div className={estilos.mas}>
                <button className={`boton ${estilos.botonVidrio}`} disabled={cargando}
                  onClick={() => void cargar(filtros, siguiente)}>
                  {cargando ? "Cargando…" : "Ver más objetos"}
                </button>
              </div>
            )}
          </div>
        </section>

        {/* ---------------------------------------------------------------- cómo funciona */}
        <section id="ayuda" className={estilos.ayuda} aria-labelledby="ayuda-titulo">
          <div className="envoltura">
            <p className={estilos.antetitulo}>Cómo funciona</p>
            <h2 id="ayuda-titulo" className={estilos.ayudaTitulo}>
              Dos caminos, un mismo objetivo: que vuelva a su dueño
            </h2>
            <div className={estilos.caminos}>
              <article className={estilos.camino}>
                <span className={estilos.caminoIcono} aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M12 3v12m0 0-4.5-4.5M12 15l4.5-4.5M4 17v2.5h16V17" />
                  </svg>
                </span>
                <h3>¿Encontraste algo?</h3>
                <ol>
                  {ENCONTRASTE.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ol>
              </article>
              <article className={`${estilos.camino} ${estilos.caminoSenal}`}>
                <span className={estilos.caminoIcono} aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <circle cx="11" cy="11" r="6.5" />
                    <path d="m16 16 4.5 4.5" />
                  </svg>
                </span>
                <h3>¿Perdiste algo?</h3>
                <ol>
                  {PERDISTE.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ol>
              </article>
            </div>
            <p className={estilos.nota}>
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M10 2.5 4 5v4.5c0 3.8 2.6 6.9 6 8 3.4-1.1 6-4.2 6-8V5l-6-2.5Z" />
              </svg>
              Por seguridad no publicamos los objetos encontrados: así evitamos que alguien reclame lo que no es suyo.
            </p>
          </div>
        </section>
      </main>
    </MarcoPublico>
  );
}
