# ADR-008: Auditoría solo de inserción

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** Backend

## Contexto

Hay que demostrar quién leyó o cambió datos personales (Ley 1581, HU-14).

## Decisión

Tabla `auditoria` particionada por mes. El rol de base de datos de la aplicación solo tiene permiso `INSERT` y `SELECT` sobre ella (sin `UPDATE` ni `DELETE`).

## Consecuencias

- Evidencia confiable aunque la aplicación tenga un error.
- Las particiones antiguas se archivan en el Data Lake.
