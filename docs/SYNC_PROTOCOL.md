# Descargas autorizadas (B28)

GET /api/v1/sync/bootstrap y /sync/changes requieren sesión válida y X-Device-ID propio.
Bootstrap crea una fotografía consistente en PostgreSQL. Historial operativo: 30 días;
entregas abiertas, borradores, correcciones pendientes, avisos sin leer y lotes autorizados
se conservan independientemente de su antigüedad.

Cada resultado es {entity_type,id,deleted,data}; id puede ser UUID o código de unidad.
Los datos usan los mismos campos de las APIs correspondientes. Conformidades incluyen
version_id, stage, user_id, occurred_at, registered_at, operation_id y detalles copiados.
assignment_options añade receivers_by_destination para selección offline.

limit: 1–200, predeterminado 100. Si next_page tiene valor, solicitar ?page=<next_page>.
Acumular todas las páginas en una transacción local; solo al final se obtiene cursor.
No reemplazar el último cursor completo con un token de página. La preparación solo
se completa al terminar; preparation_expires_at no sustituye la sesión central.

GET /sync/changes?cursor=<último cursor completo> materializa el alcance actual y lo
compara con la fotografía anterior. Incluye upserts y tombstones (deleted=true,data=null)
por bajas, pérdida de acceso y salida de la ventana histórica. Las entidades necesarias
como referencias históricas pueden permanecer con active=false.
Aplicar todas las páginas juntas y entonces guardar el cursor nuevo.

Un cambio de permisos durante una descarga paginada produce CURSOR_SCOPE_CHANGED:
descartar únicamente las páginas incompletas y reiniciar changes desde el cursor completo.
Si era el primer bootstrap, reiniciar bootstrap. CURSOR_EXPIRED (410) exige bootstrap
nuevo que reemplaza el caché confirmado, conservando siempre la cola local de intenciones.
El cursor está firmado, vence y pertenece a la cuenta/dispositivo; nunca autoriza acceso.

Decisión de implementación: fotografías y diferencias persistidas, sin depender de
timestamps mutables o de ordenar UUID al azar. Retención inicial 24 h y máximo 20.000
entidades configurables (SYNC_CURSOR_TTL_HOURS / SYNC_MAX_ENTITIES). Limpieza operativa
de fotografías vencidas se documentará en B40. No borrar SyncOperation ni outbox local
como parte de esta limpieza.
