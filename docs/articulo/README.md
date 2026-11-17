# Artículo IEEE

Artículo en formato de conferencia IEEE (`IEEEtran`), en español con *abstract* en inglés.

| Archivo | Qué es |
| --- | --- |
| `articulo.tex` | El artículo. Las figuras están dibujadas con TikZ/pgfplots dentro del mismo archivo |
| `referencias.bib` | Referencias en BibTeX (estilo `IEEEtran`) |
| `articulo.pdf` | PDF compilado, para revisar sin compilar |

## Compilar en Overleaf

1. En Overleaf: **New Project → Upload Project** y sube un `.zip` con `articulo.tex` y `referencias.bib` (o crea un proyecto en blanco y sube los dos archivos).
2. **Menu → Compiler: pdfLaTeX**. **Main document: `articulo.tex`**.
3. **Recompile**. Overleaf corre BibTeX solo.

## Compilar en local

```bash
latexmk -pdf articulo.tex
```

Necesita TeX Live con los paquetes `ieeetran` (texlive-publishers), `babel-spanish` (texlive-lang-spanish), `pgfplots` y `tikz`.

## De dónde salen las cifras

Todos los números del artículo salen del repositorio. Si cambian, hay que actualizar el texto:

| Sección | Fuente |
| --- | --- |
| Calidad del emparejamiento (Tabla II, Fig. 3) | `docs/adr/013-umbral-y-penalizacion-color.md` |
| Predicción del analista (backtest) | `docs/adr/015-agente-analista.md` |
| Pruebas de carga (Tabla III) | `pruebas-carga/resultados/portatil-200u.md` y `portatil-pico-100u.md` |
| Citus (Tabla IV) | `pruebas-carga/resultados/citus-portatil.md` |
| Fallos de concurrencia e índices | `docs/adr/021-resultados-fase-6.md` |
| Restauración del respaldo | prueba `respaldo verificar` en el portátil (1 M de reportes, 182 s) |

## Antes de entregar

- La referencia [20] apunta al repositorio de GitHub. Si el repositorio sigue privado, háganlo público o quiten esa referencia.
- Revisen la ortografía de los nombres de los autores.
