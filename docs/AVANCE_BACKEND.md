# Avance backend SITRAP

Rama exclusiva: `agente-backend`. Especificación: los cuatro documentos revisión 3,
leídos íntegramente el 2026-10-02. Frontend, fusiones y despliegue Azure excluidos.

## Estado

B01 en implementación. Última tarea terminada: ninguna.

## Registro por tarea

Se anotarán alcance, pruebas y commit individual. El hash del commit que contiene
una fila se resuelve con `git log --oneline --grep='Bxx'`; las siguientes tareas
añadirán los hashes ya conocidos sin reescribir commits.

## Entorno y bloqueos

- Worktree Git sin remoto configurado; URL de GitHub solicitada. No impide commits
  locales ni tareas independientes. No declarar publicación hasta verificar push.
- Python 3.12 encontrado en el runtime local de Codex; venv aislado `.venv`.
- PostgreSQL 18 instalado; preparar clúster de pruebas aislado, sin tocar bases existentes.

## Pendientes y siguiente paso

B01–B39 pendientes, ejecutar en orden de dependencias de 04 §8. B40 se limita a
configuración e instrucciones después de B39; despliegue real después de integrar frontend.

## Decisiones para frontend

- Prefijo `/api/v1`, rutas sin barra final. OpenAPI incremental solo anuncia rutas reales.
- Sesiones de 12 horas y preparación offline de 7 días; variables configurables.
- Cantidades como strings Decimal, UUID de negocio, UTC en tiempos y America/Lima en fechas.
