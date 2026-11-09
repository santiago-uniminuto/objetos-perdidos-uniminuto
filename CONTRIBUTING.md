# Cómo trabajamos

## Ramas

- `main`: siempre desplegable. Nadie hace push directo; todo entra por Pull Request.
- Ramas de trabajo: `<tipo>/<frente>-<tema>`, por ejemplo `feat/backend-reportes`, `feat/ia-matcher`, `fix/frontend-filtros`, `docs/ieee-metodologia`.

## Commits

Formato *Conventional Commits* en español:

```text
feat(reportes): registrar reporte con consentimiento
fix(publico): ocultar foto de documentos
docs(adr): ADR-012 clave de partición de Citus
test(matching): recall@5 con set etiquetado
chore(infra): perfil escala en docker-compose
```

## Pull Requests

1. Actualiza tu rama con `main` antes de abrir el PR: `git pull --rebase origin main`.
2. CI en verde (lint + pruebas).
3. Al menos **1 aprobación** de otro integrante.
4. Si el PR toma una decisión de arquitectura, agrega un ADR en `docs/adr/`.

## Flujo diario

```bash
git checkout main
git pull
git checkout -b feat/<frente>-<tema>
# ... trabajar ...
git add -A
git commit -m "feat(<modulo>): <qué hace>"
git push -u origin feat/<frente>-<tema>
# abrir el PR en GitHub
```

## Frentes

| Frente | Carpetas principales |
| --- | --- |
| Backend + PostgreSQL | `backend/`, `infra/postgres/` |
| Datos | `datos/`, `pruebas-carga/` |
| IA | `agentes/` |
| Frontend + DevOps | `frontend/`, `infra/`, `.github/` |
