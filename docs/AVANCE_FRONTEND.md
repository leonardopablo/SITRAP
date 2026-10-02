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
| F02 | Implementado | `feat: crear base visual` | 4 pruebas acumuladas; build; contraste calculado de pares de texto | Validación Android y auditoría completa F38 |
| F03–F38 | Pendientes; continuar en orden elegible | — | — | Dependencias de documento 03 |
| F39 | Reservado postfusión | — | — | Integración y piloto |

## Supuestos de contrato

Fuente: documento 04 §§2–5. `/api/v1`, sesiones Django/CSRF, cantidades string decimal, UUID estables, errores normalizados. Al disponer de OpenAPI real, regenerar tipos y contrastar payloads y respuestas; no inventar garantías de servidor.

## Continuación

Siguiente: F03/F04 y F05. Ejecutar verificaciones por incremento y commit individual. No habilitar operaciones simuladas como confirmaciones reales.
