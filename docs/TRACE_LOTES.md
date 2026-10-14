# Recorrido visual de lotes

El panel **Administración → Trazabilidad** consulta el origen y las entregas
asociadas a un lote. Solo una cuenta con ADMIN global vigente puede abrir
`GET /api/v1/lots/{id}/trace`; las demás reciben 403. El listado `/lots`
admite `?code=` para buscar por código dentro del ámbito del usuario.

Cada entrega es una rama independiente del lote. La respuesta pagina las
entregas con `limit` (máximo 200) y `offset`, y devuelve `count` y `next_offset`;
no oculta las ramas posteriores. Muestra cantidad y personas del documento
vigente, pero conserva las confirmaciones físicas aunque pertenecieran a una
versión anterior. Una entrega cancelada permanece en el historial. Los
`BORRADOR` no enviados no representan recorridos y no se incluyen entre las
ramas paginadas: `draft_count` informa cuántos existen sin ocultar su existencia.

La hora del origen es la publicación de la versión de producción; la fecha
de ordeño no implica una hora de ordeño. Para recogida y recepción se usa
`Conformity.occurred_at`, declarada por el dispositivo; `registered_at` indica
cuándo quedó registrada en el servidor. El intervalo se calcula únicamente
si ambas confirmaciones existen y recepción no precede a recogida. No es GPS,
tiempo exacto de conducción ni prueba de temperatura o conservación.

El recorrido es de solo lectura. No altera producción, entregas, avisos,
correcciones, conformidades ni las reglas de asignación de cantidades.
