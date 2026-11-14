# Frontend (Next.js 16, export estático)

Portal público (objetos **perdidos**, ADR-016) y panel del personal. Caddy lo sirve compilado (ADR-017).

| Ruta | Quién | Qué |
|---|---|---|
| `/` | Público | Etiquetas de objetos perdidos, filtros por sede, categoría, zona y fecha |
| `/objeto/?id=` | Público | Etiqueta de un objeto e instrucciones |
| `/admin/login/` | Personal | Ingreso con correo institucional |
| `/admin/olvide/`, `/admin/restablecer/?token=` | Personal | Restablecer contraseña con enlace de un solo uso |
| `/admin/` | Admin y auditor | Analítica: resumen del agente analista, indicadores, predicción semanal, mapa de calor |
| `/admin/reportes/`, `/admin/hallazgos/` | Admin | Listas con miniatura, filtro por estado y "ver más" |
| `/admin/reportes/nuevo/` | Admin | Registro en 4 pasos: dueño (buscar o crear + autorización Ley 1581), qué es, dónde y cuándo (plano de zonas), descripción y fotos |
| `/admin/hallazgos/nuevo/` | Admin | Registro en 3 pasos (sin dueño) |
| `/admin/reportes/ver/?id=`, `/admin/hallazgos/ver/?id=` | Admin | Detalle: fotos (ampliar, agregar, borrar con confirmación), datos y dueño (lectura auditada) |
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

## Sistema de diseño

Componentes reutilizables en `componentes/ui/`:

- `Avisos`: toasts que entran y salen por el mismo lado.
- `Confirmar`: `<dialog>` nativo para acciones que no se pueden deshacer.
- `Insignia`: estado con texto; el color solo acompaña.
- `Vacio`: estado vacío con caja isométrica.
- `Pasos`: indicador de pasos.
- `Campo`: etiqueta, ayuda y error.
- `PlanoZonas`: selector de zona en estilo blueprint.
- `SubirFotos`: vista previa y validación de las fotos.
- `Foto`: imagen con respaldo si el archivo falta.

Reglas de movimiento:
- Animaciones de interfaz de menos de 300 ms, con `--ease-out` fuerte.
- Los botones se hunden al presionarlos (`scale(0.97)`).
- Solo una tipografía en movimiento: la confirmación de registro.
- Siempre se respeta `prefers-reduced-motion`.

## Diseño

- Base institucional azul tinta (`#14284a`) y amarillo de señalización (`#f4c21a`) para lo accionable.
- Los objetos públicos son **etiquetas de objeto perdido**: cartulina kraft con ojal. Es el único elemento ilustrado.
- Tipografías: Bricolage Grotesque para títulos y Atkinson Hyperlegible para el texto (pensada para lectura fácil en celulares). Ambas van dentro del build, sin CDN.
- Gráficas en SVG propio:
  - La predicción se distingue por **textura y leyenda**, no solo por color.
  - El mapa de calor usa una rampa de un solo tono con el número en cada celda.
  - Cada gráfica tiene una vista en tabla.
