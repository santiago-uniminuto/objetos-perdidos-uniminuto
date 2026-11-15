# ADR-019: Sedes reales de UNIMINUTO e intentos de entrega fallidos

- **Estado:** aceptada
- **Fecha:** 2026-11-14
- **Responsable:** Equipo completo

## Contexto

1. El catálogo tenía pocas sedes de ejemplo. Para no rehacer la analítica más adelante, el sistema debe quedar "global" desde ya, con las sedes reales de UNIMINUTO.
2. Si el supuesto dueño no pasa la verificación (documento o pregunta de control), el objeto quedaba en un limbo: la coincidencia seguía "por entregar" para siempre.

## Decisión (aprobada por el equipo)

**Sedes.** La migración `0007` carga 68 sedes presenciales con su región (Bogotá-Cundinamarca-Boyacá, Antioquia-Chocó, Caribe, Centro Occidente, Centro Sur, Oriente y PCIS como "Nacional"), sus direcciones conocidas y las 11 zonas en cada una. Se excluye UNIMINUTO Virtual, que no tiene oficina física de objetos perdidos. La sede 1 sigue siendo Calle 80 (sede principal), así que los datos existentes no cambian.

- El portal y la analítica agrupan las sedes por región en el selector.
- El admin y el auditor pueden ver la analítica de **cualquier** sede o de todas. Son solo agregados (conteos, zonas, horas), sin datos personales; operar (registrar, verificar, entregar) sigue limitado a la sede del admin.

**Intentos de entrega.** Regla "3 intentos y se libera":

- Cada intento fallido se guarda en `intento_entrega` con un motivo obligatorio: `documento`, `pregunta_control` u `otro`. El intento queda también en la auditoría.
- El acta solo se pide cuando sí se entrega.
- Al **tercer** fallo, la coincidencia pasa a `rechazada` ("Verificación fallida 3 veces"). El reporte y el hallazgo vuelven a `publicado`, solo si no tienen otra coincidencia verificada, y el matcher puede sugerir otro dueño.
- **No se marca a la persona.** Una lista negra de personas sería un dato personal sensible sin base legal clara (Ley 1581), y un fallo puede ser honesto: olvidó el carné, o no recuerda un detalle. El rastro queda en la auditoría por si hay un patrón de abuso, y lo revisa una persona.

## Consecuencias

- La bandeja muestra "N de 3 intentos fallidos", y el diálogo avisa cuando el intento es el último.
- La analítica global con 68 sedes depende del agente analista; las sedes sin datos muestran "aún no hay semanas suficientes".
- Bajar la migración borra `intento_entrega` y las columnas nuevas, pero conserva las sedes (pueden tener objetos asociados).
