# Frontend (Next.js 16, export estático)

Portal público (objetos **perdidos**, ADR-016) y panel del personal. Caddy lo sirve compilado (ADR-017).

| Ruta | Quién | Qué |
|---|---|---|
| `/` | Público | Etiquetas de objetos perdidos, filtros por sede, categoría, zona y fecha |
| `/objeto/?id=` | Público | Etiqueta de un objeto e instrucciones |
| `/admin/login/` | Personal | Ingreso con correo institucional |
| `/admin/olvide/`, `/admin/restablecer/?token=` | Personal | Restablecer contraseña con enlace de un solo uso |
| `/admin/` | Admin y auditor | Analítica: resumen del agente analista, indicadores, predicción semanal, mapa de calor |
| `/admin/cuenta/` | Admin y auditor | Cambiar contraseña |

## Desarrollo

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000, reenvía /api a http://localhost:8080 (Caddy + API del Compose)
npm run lint         # tipos
npm test             # formatos en español
npm run build        # genera out/ (lo mismo que hace la imagen de Caddy)
```

## Diseño

- Base institucional azul tinta (`#14284a`) y amarillo de señalización (`#f4c21a`) para lo accionable.
- Los objetos públicos son **etiquetas de objeto perdido**: cartulina kraft con ojal. Es el único elemento ilustrado.
- Tipografías: Bricolage Grotesque para títulos y Atkinson Hyperlegible para el texto (pensada para lectura fácil en celulares). Ambas van dentro del build, sin CDN.
- Gráficas en SVG propio:
  - La predicción se distingue por **textura y leyenda**, no solo por color.
  - El mapa de calor usa una rampa de un solo tono con el número en cada celda.
  - Cada gráfica tiene una vista en tabla.
