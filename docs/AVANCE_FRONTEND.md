# Avance frontend SITRAP

## Reglas y estado

- Rama exclusiva: `agente-frontend`. Sin cambios en backend ni fusiones.
- Leídos los cuatro documentos SITRAP, revisión 3 (2026-10-02).
- API/OpenAPI aún ausentes. Las dependencias Bxx se cubren provisionalmente con contrato documental y mocks tras el mismo cliente. **Implementado frontend no significa integrado con backend.**
- F39 reservado para después de fusionar, por instrucción del usuario.
- No hay remoto Git configurado: publicación pendiente; no se ha hecho push.
- Cada fila refiere al commit por su mensaje único; los hashes se incorporan al siguiente incremento para evitar autorreferencias.

## Tareas y verificaciones

| Tarea | Estado frontend | Commit | Verificación | Pendiente real |
|---|---|---|---|---|
| F01 | Implementado | `aab838b` | 2 pruebas navegación; build OK | B01/API base |
| F02 | Implementado | `a32425d` | 4 pruebas; build OK; contraste texto 4,71:1–10,71:1 | Validación Android y auditoría completa F38 |
| F03 | Implementado | `6a6e6c9` | Build y 4 pruebas; SVG vectorial local, variantes 32/48 px, favicon | Aprobación institucional de identidad |
| F04 | Implementado | `2ec90ce` | Build; 4 pruebas; SVG locales estáticos, conjunto 2498 bytes | Medición Android; integración de éxitos en F37 |
| F05 | Implementado con adaptador simulado | `d3cc5d0` | Build y 7 pruebas; CSRF/login/error/cambio obligatorio/expiración | B04; cookies/rotación/fuerza bruta reales no verificadas |
| F06 | Implementado con adaptador simulado | `fe140e7` | Build; 8 pruebas; ruta ajena bloqueada, logout limpia identidad | B05; servidor debe comprobar ámbitos; vistas de navegación identificadas como pendientes |
| F07 | Implementado contra OpenAPI provisional | `feat: conectar contrato api` | Generación de tipos, build; 10 pruebas incluyendo errores red/HTML y replay con UUID/payload estable | B06 y OpenAPI exportado real; no integrado |
| F08–F38 | Pendientes; continuar en orden elegible | — | — | Dependencias de documento 03 |
| F39 | Reservado postfusión | — | — | Integración y piloto |

## Supuestos de contrato

Fuente: documento 04 §§2–5. `/api/v1`, sesiones Django/CSRF, cantidades string decimal, UUID estables, errores normalizados. Al disponer de OpenAPI real, regenerar tipos y contrastar payloads y respuestas; no inventar garantías de servidor.

- F05: se supone respuesta CSRF `{csrf_token}`, `/auth/me` con `id/username/name/change_password_required/assignments/capabilities`, login `{username,password}` y cambio `{current_password,new_password}`. Nombres a contrastar con B04/OpenAPI. Mínimo local propuesto de 12 caracteres; servidor debe definir política final.
- `VITE_API_MODE=mock` por defecto, `http` para API real. Un solo cliente, adaptador elegido al compilar; sin fallback silencioso. Mock de sesión solo en memoria (recarga exige login), sin persistir contraseñas/tokens. Cambio de clave simulado valida la UI, no cambia una credencial real.
- F07: `frontend/contracts/openapi.provisional.json` es un subconjunto explícitamente provisional, derivado del documento, NO extraído del backend. `npm run api:generate` reproduce tipos. Supuesto batch `{events}` / `{results}`; confirmar con B29. Payload específico se añadirá junto al incremento que lo consume. TypeScript fijado a 5.9.3 por peer compatible de openapi-typescript 7.13.0 (sin forzar dependencias).

## Continuación

Siguiente: F08, F09 y F10. Ejecutar verificaciones por incremento y commit individual. No habilitar operaciones simuladas como confirmaciones reales.
