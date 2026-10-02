# Avance backend SITRAP

Rama exclusiva: `agente-backend`. Cuatro documentos revisión 3 leídos íntegramente.
Última tarea terminada: **B33**. Siguiente elegible: **B34**.
No se modificó frontend, no hubo fusiones ni despliegues.

## Commits y pruebas

| Tarea | Commit | Verificación al cierre |
|---|---|---|
| B01 | `e85720a` | Django/DRF, configuración por entorno, lock con hashes, health y arranque WSGI/ASGI: 2 pruebas; check y OpenAPI correctos. |
| B02 | `043fb22` | PostgreSQL 18 aislado, runner pytest y CI: 3 pruebas acumuladas; migraciones reales y rollback. Workflow remoto aún no ejecutado. |
| B03 | `bed8229` | Usuario UUID, roles sembrados, ámbitos GLOBAL/UBICACION, períodos, unicidad y FK protegidas: 11 pruebas acumuladas; migración limpia. |
| B04 | `f3919dc` | 17 pruebas acumuladas: CSRF en login/mutaciones, cookies, expiración/logout, contraseñas y revocación de otras sesiones, inactivos y límite de intentos; Ruff y OpenAPI válidos. |
| B05 | `416efcb` | 22 pruebas acumuladas; aislamiento por centro/ID, vigencias, revocaciones, ADMIN sin permisos operativos y capacidades en me. |
| B06 | `62e1310` | 27 pruebas acumuladas; dispositivos propios, hash canónico, replay, conflictos, rollback y duplicado concurrente en PostgreSQL. |
| B07 | `a2d8a87` | 32 pruebas acumuladas; auditoría atómica, rollback ante fallo, redacción de secretos y trigger PostgreSQL contra UPDATE/DELETE. |
| B08 | `da76a5e` | 37 pruebas acumuladas; API ADMIN, contraseña temporal, reset, revocación de sesiones, bajas, ámbitos sin superposición y bootstrap inicial. |
| B09 | `f84b2f0` | 40 pruebas acumuladas; catálogos autorizados, altas idempotentes, bajas auditadas, centro válido y ausencia de stock. |
| B10 | `553001f` | 42 pruebas acumuladas; unidades/presentaciones/especies/turnos, contenido positivo, bolsa indivisible, sin conversión KG/L; OpenAPI sin warnings y conexiones de test cerradas. |
| B11 | `5d19be6` | 44 pruebas acumuladas; opciones mínimas por origen/destino, defaults solo con una opción, inactivos excluidos y acceso entre centros negado. |
| B12 | `7ea58a5` + `de2aff2` | 48 pruebas acumuladas; animales/estancias, centros válidos, movimientos solo ADMIN y exclusión de solapamiento incluso con dos transacciones concurrentes. |
| B13 | `07f505e` | 51 pruebas acumuladas; UUID, vacío/cero, vaca/fecha/centro válidos, replay y carrera de edición con una sola versión ganadora; contrato exacto. |
| B14 | `7f48032` | Suite completa: 54 pruebas; luego 4 de confirmación al parametrizar cero/vacío. Suma, versión exacta, lote único, carrera entre productores e inmutabilidad publicada. |
| B15 | `4f29ffc` | Suite 58 pruebas; luego 6 de borrador/anulación, incluida carrera con dos productores. Unicidad parcial, historia conservada y reemplazo con lote propio. Sin endpoint público. |
| B16 | `7f1d82c` | 60 pruebas de suite; consultas P/T/R/A, borradores ocultos a T/R, procedencia sin detalle por vaca, versiones/timeline y catálogos vinculados. |
| B17 | `3310aa9` | 62 pruebas: borrador y línea atómicos, participantes, bolsas enteras, replay y versión obsoleta. OpenAPI validado. |

| B18 | `4ce20df` | 64 pruebas: destinatario, unicidad, lectura idempotente y rollback transaccional. Migración aplicada y OpenAPI validado. |

| B19 | `b214b24` | Publicación/reserva, carrera de productores, rollback de aviso, guardas de anulación y documentos inmutables. Verificación completa al cierre: 67 pruebas. |

| B20 | `6b6c28a` | 7 pruebas pertinentes: revisión, historia, reserva vigente, exceso, cancelación, idempotencia y contrato exacto. |

| B21 | `e751464` | 10 pruebas pertinentes: versión exacta, una etapa física, firma asignada, aviso a R, carrera revisión/recogida y contrato. |

| B22 | `6a44f55` | Suite completa: 75 pruebas; recepción única/asignada, estado EN_CAMINO, documento exacto y avisos a emisor/conductor. |

| B23 | `db2b4cd` | 77 pruebas de suite; luego 6 pertinentes incluyendo aumento/reducción, reserva máxima, aprobadores fijos, consulta privada, propuesta inmutable y recepción bloqueada. |

| B24 | `d326bd7` | 10 pruebas pertinentes y luego 5 de aceptación incluyendo concurrencia; ambos órdenes, revocación, ADMIN denegado, rollback y estado/firmas físicas conservados. |

| B25 | `c192d19` | Suite completa: 86 pruebas; rechazo/retiro después de una aceptación, recepción reabierta y carrera con segunda aceptación. |

| B26 | `e32f9b8` | 8 pruebas pertinentes: ADMIN, replay, receptor anterior/nuevo, firmas intactas, recepción y cualquier corrección histórica bloquean. |

| B27 | `d33a8be` | Suite: 90 aprobadas y una expectativa antigua de B15 corregida al abrir /void; luego 8 pruebas pertinentes. Rectificación/reservas, historia, vacas inactivas posteriores, anulación y carrera con publicación. |

| B28 | `f2ec6f2` | 4 pruebas pertinentes: paginación estable, abierta antigua, revocaciones/tombstones, baja de catálogo, cursor ajeno/vencido, scope cambiante y contrato. |

| B29 | `dbab7ee` | 14 pruebas pertinentes: orden inverso, replay, espera/reanudación, rechazo propagado, ciclos entre lotes y carrera, límites, tipo online y contrato. |

| B30 | `4de471b` | 19 pruebas pertinentes; luego 5 de sesión/límites. Caducidad, CSRF, otra cuenta, revocación de rol/dispositivo, preparación vencida y expiración absoluta. |

| B31 | `56b50e5` | Suite completa: 117 pruebas. Suscripción/propiedad/replay, HTTPS, claves, logout/baja, secretos, cifrado real local; pip check y descarga con hashes correctos. |

| B32 | `4e653f7` | 23 pruebas pertinentes: 11 tipos de aviso, destinatarios/suscripciones activos, deduplicación, rollback conjunto y regresión de flujos/contrato. |

| B33 | `feat: entregar avisos push (B33)` (este commit) | 35 pruebas pertinentes: leases, concurrencia, reinicio, errores HTTP/red, timeout, no redirecciones, baja de suscripciones y latido. |

Obtener hash exacto de cada tarea: `git log --oneline --grep='B04'`.
Cada funcionalidad tiene su propio commit y se publica en origin/agente-backend.

## Entorno reproducible

- Python 3.12.14 disponible en `C:/Users/pablo/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
- Entorno del proyecto: `.venv/Scripts/python.exe`; versiones y hashes en `requirements.txt` y `requirements-dev.txt`.
- PostgreSQL 18.6 de `C:/Program Files/PostgreSQL/18/bin`.
- Clúster exclusivo de desarrollo: `.local/pgdata`, escucha `127.0.0.1:55432`.
  Base `sitrap`; pytest crea/destruye `test_sitrap`. Secretos solo en archivos ignorados.
- `scripts/local-postgres.ps1 Start|Stop|Status`; requiere el mismo usuario Windows que creó el clúster.
- Verificación: `scripts/check.ps1`. Aplicar migraciones pendientes: `.venv/Scripts/python.exe manage.py migrate`.
- El sandbox impide escribir metadatos Git del worktree en `../SITRAP/.git`;
  commits requieren ejecución autorizada fuera del sandbox. No cambiar de rama.
- Las pruebas corren contra PostgreSQL real. No se admite SQLite.
- Al editar desde PowerShell, usar UTF-8 explícito o JSON con Unicode escapado;
  una tubería con codificación ASCII dejó inicialmente filas del avance sin reemplazar.
  Este informe corrige el estado completo verificándolo contra el log Git.

## Bloqueos

No hay bloqueo funcional actual. Remoto autorizado: https://github.com/leonardopablo/SITRAP.git.
B01-B32 publicados y rama local sigue origin/agente-backend. No se ha verificado todavía el resultado del workflow remoto.

## Decisiones que afectan al frontend

- Prefijo `/api/v1`, sin barra final. `docs/openapi.yaml` contiene solo rutas implementadas.
- Autenticación por cookie de sesión, no bearer tokens. Pedir `GET /auth/csrf`,
  enviar `X-CSRFToken` en login y mutaciones, renovar CSRF tras login.
- `GET /auth/me` devuelve UUID, username, name, password_change_required y asignaciones
  vigentes. Incluye ubicaciones y capacidades por rol y ubicación.
- Sesión de 12 horas y preparación offline de 7 días configurables.
- `401 SESSION_EXPIRED` conserva la cola; `403 CSRF_FAILED` exige renovar CSRF.
  Errores uniformes: code, message, field_errors, retryable. Validación: 422.
- Contraseña temporal obliga al cambio; cambio de contraseña invalida otras sesiones.
- ADMIN no obtendrá conformidades operativas por ser administrador.
- B03 solo añadió la ubicación mínima necesaria para las FK; API de catálogos pendiente B09.
- Cantidades serán strings Decimal; UUID de negocio, tiempos UTC y fechas America/Lima.
- La revisión de login usa límites persistentes por usuario e IP; no confiar en X-Forwarded-For
  sin configurar explícitamente un proxy conocido. B40 debe documentar proxy y limpieza de buckets.

## Pendientes y reanudación

**B33–B39 pendientes**. Seguir dependencias exactas de 04 §8:
B05 autorización → B06 dispositivos/idempotencia → B07 auditoría;
después B08–B17 y B18 antes de B19. B23 debe completar la guarda de recepción B22.
B27 requiere B25, B28 requiere B18/B27, B29–B30 sincronización.
B31 requiere B18; B32 requiere B25/B26/B31; B33 worker.
B34–B38 métricas/PDF y B39 contrato/demo solo tras B30/B33/B38.

**B40 pendiente de preparación** después de B39. Dejar configuración e instrucciones
de web/worker, secretos, HTTPS, backup/restauración; el despliegue real queda reservado
hasta integrar frontend. No declarar B40 terminado ni ejecutar Azure.

Para retomar: comprobar rama y status, leer este informe, revisar el último commit,
aplicar migraciones y ejecutar las pruebas pertinentes; continuar en B33, sin rehacer B01–B32.

B06: registrar dispositivo con POST /devices {id,name}; GET /devices/current usa
X-Device-ID. El sobre de comandos está implementado en servicios internos,
no hay aún endpoint /sync/events (B29). Replays revalidan permisos actuales;
authorize solo verifica permisos, y el handler verifica estados dentro de la transacción.

B07: toda auditoría se escribe dentro de la transacción del cambio. El trigger
impide UPDATE/DELETE; el rol de BD de producción deberá carecer de TRUNCATE/DDL
y no ser propietario (preparar en B40). No se afirma inviolabilidad frente al dueño de BD.

B08: alta de cuenta recibe id UUID, username, name, temporary_password; no devuelve
la clave. Reset recibe temporary_password y obliga cambio. PATCH de asignación
solo cierra/reabre ends_at; para cambiar rol/centro se cierra y crea otra con UUID nuevo.
Crear primer ADMIN: manage.py bootstrap_admin --username <usuario> --name <nombre>;
pide clave por consola (o SITRAP_BOOTSTRAP_PASSWORD en entorno protegido), obliga cambio.
B31 deberá integrar bajas de cuenta y logout con desactivación de suscripciones push.

B09: identificadores UUID requeridos en altas online. PATCH cambia nombre/activo
o habilitado; código/tipo/unidad y pares centro-producto no se reasignan.
Unidad mínima L/KG/UN sembrada para la FK de producto; su API se completa en B10.
B16 ampliará catálogos/procedencia de T/R mediante entregas autorizadas.

B10: /units usa códigos L/KG/UN; presentaciones usan content_base string decimal
y allows_fraction. La compatibilidad del piloto se comprueba al operar: unidad L,
contenido 1 y bolsas enteras. Un catálogo genérico no habilita procesos operativos.

B11: GET /assignment-options exige origin_id; destination_id opcional. Sin destino
y con varios disponibles, receivers queda vacío hasta elegir uno. Destinos son
puntos de venta activos con receptor vigente; no existe en el modelo una restricción
de rutas centro-destino adicional. Solo id/name, sin datos de cuenta privados.

B12: estancias por fecha operativa en intervalos [starts_on,ends_on); fin null abierto.
Alta animal requiere stay_id, center_id y starts_on. Un movimiento ADMIN cierra
atómicamente la estancia abierta anterior; PRODUCCION no mueve entre centros.
Lectura de animal conserva acceso histórico a sus centros autorizados; PATCH exige
estancia actual en el centro autorizado. GET stays filtra centros del operador.
Migración usa btree_gist y ExclusionConstraint, conforme a
https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/constraints/.

Corrección B12: la primera publicación conservó OpenAPI anterior por un warning
de etiquetas del enum. Se corrigió el nombre usando las etiquetas reales, se generó
el contrato sin warnings y se añadió test de igualdad del esquema generado/versionado.
48 pruebas y makemigrations --check pasan. No avanzar con checks fallidos.

B13: entity_id y /milkings/{id} identifican ordeño; payload de alta incluye
production_id y version_id separados, centro/producto/fecha/turno y details.
Cada detalle recibe animal_id y liters string o null; null nunca se convierte a cero.
PATCH reemplaza el detalle del borrador completo y requiere expected_version.
La confirmación llegará en B14; unicidad parcial en BD y anulación en B15.
No habilitar piloto antes de completar esas dependencias.

B14: POST /milkings/{id}/confirm usa MILKING_CONFIRM y payload {version_id,lot_id},
con expected_version. No admite total libre. Exige valores para todas las vacas
activas/hembras con estancia válida al día y total positivo. Devuelve lot_id.
La confirmación no crea avisos de transporte. Versiones publicadas y detalles
protegidos por triggers; solo transición documental PUBLICADA a SUPERADA permitida.
Intento de consultar CI por API pública no accesible; CI remoto sigue sin verificarse.

B15: MILKING_CREATE acepta replaces_id opcional de ordeño ANULADO del mismo
centro/producto. Anulación solo servicio interno void_internal: motivo y versión,
producción ANULADA y voided_at atómicos. B19 debe incorporar bloqueo por
asignaciones activas antes de permitir publicar entregas; B27 expone /void al final.

B16: GET /transfers, /transfers/{id}, /timeline y /lots; T/R solo asignados
o participantes históricos con rol/ámbito vigente. Borradores solo P del origen/A.
Procedencia del lote no expone detalles por vaca a T/R. Catálogos incluyen
productos/presentaciones/ubicaciones de sus entregas autorizadas para resolver IDs.
Modelos de conformidad introducidos para consultas históricas; creación por
servicios se habilita en B19/B21/B22. Capacidades no anuncian acciones aún no implementadas.

B17: POST/PATCH /transfers usa sobre TRANSFER_CREATE/UPDATE; payload completo con
version_id, line_id, lot_id, presentation_id, units, destination_id, driver_id, receiver_id.
El piloto opera una línea por entrega; no reserva cantidades ni notifica en borrador.
Transportista y receptor deben ser cuentas diferentes con asignación vigente.

B18: GET /notifications devuelve resultados paginados y unread_count propio.
POST /notifications/{id}/read con objeto vacío marca lectura sin confirmar negocio.
El aviso interno comparte transacción con el hecho; push se incorporará en B31-B33.

B19: POST /transfers/{id}/send recibe TRANSFER_SEND, expected_version y payload
{version_id}. Publicar crea conformidad origen y PICKUP_REQUESTED atómicamente.
Reservas documentales incluyen entregas publicadas no canceladas, incluso recibidas;
no representan stock físico. B23 ampliará reserva a max(vigente,propuesta).
Anulación de producción bloqueada con entregas activas. Cuenta operativa se bloquea
con FOR NO KEY UPDATE para serializar revocaciones permitiendo referencias FK de avisos.
Se corrigió también el orden de imports de la migración B18 detectado por Ruff.

B20: /revise requiere nueva version_id/line_id, units, destination_id, driver_id,
receiver_id y reason. No permite cambiar lote, origen ni presentación publicada.
/cancel requiere reason; ambas acciones exigen expected_version. Aviso de revisión
al conductor actual y anterior si cambió. Cancelar no altera documentos publicados.

B21: /pickup usa TRANSFER_PICKUP con payload {version_id}; servidor copia las
líneas y rechaza cantidades libres. Una sola RECOGIDA en toda la historia del
traslado. Conformidades protegidas por trigger contra cambios/borrado.
Capacidades del detalle acumulan todos los roles operativos vigentes de la cuenta.

B22: /receive usa TRANSFER_RECEIVE con {version_id}; copia documento y crea
RECEPCION una sola vez. No acepta cantidad distinta ni incidencias. B23 incorpora
CORRECTION_PENDING antes de habilitar propuestas; flujo aún no listo para piloto.

B23: crear en /transfers/{id}/corrections con entity_id del traslado y expected_version
del traslado. Payload correction_id, version_id/line_id nuevos, units y reason.
El resultado devuelve lock_version del traslado y correction con su propia lock_version;
B24 decisiones usarán entity_id/expected_version de la solicitud. Detalle de entrega
incluye pending_correction_id. GET /corrections/{id} muestra antes/después y aprobadores.
La propuesta mantiene max(vigente,propuesta) reservado; no cambia cantidad vigente
ni estado físico. B22 ya bloquea recepción pendiente. Aprobadores/propuesta fijos por BD.

B24: /corrections/{id}/accept usa entity_id/expected_version de la solicitud y
payload {version_id} de propuesta. Primera aceptación sube lock_version; segunda
con versión vieja exige revisar y reenviar una intención nueva. Nunca autoaprobar
tras conflicto. Solo dos ACEPTAR aplican; decisiones e historia física son inmutables.
Después de aplicar en EN_CAMINO sigue faltando la recepción física.

B25: /reject recibe {version_id,reason}; /withdraw {reason}, con versión de
solicitud. Solo aprobador aún sin decisión puede rechazar; solo solicitante con
PRODUCCION vigente puede retirar. La propuesta pasa a RETIRADA, la cantidad
vigente no cambia y la recepción que faltaba vuelve a estar disponible.

B26: /reassign-receiver es administración exclusivamente online con id UUID estable,
expected_version, nuevos version_id/line_id, receiver_id y reason (sin sobre offline).
Devuelve Transfer directamente; conserva respuesta para reintentos idénticos.
No genera conformidad origen/recogida/recepción por ADMIN; solo revisión auditada.
Cualquier solicitud histórica, incluso retirada/rechazada, impide reasignación.

B27: /rectify recibe MILKING_RECTIFY, nueva version_id, reason y details completos
exactamente de las vacas del documento original, aun si fueron desactivadas después.
No cambia fecha/turno/centro/producto. /void recibe MILKING_VOID y reason; ambos
solo online al implementar B29. GET ordeño incluye versions con historia completa.
Rectificar cubre reserva max(vigente,propuesta); anular bloquea vínculos activos.

B28: protocolo exacto en docs/SYNC_PROTOCOL.md. Bootstrap/changes requieren
X-Device-ID propio; next_page solo pagina, cursor solo aparece al completar.
Fotografía PostgreSQL REPEATABLE READ y diferencias por entidad; sin omitir bajas.
TTL inicial 24 h, límite 20.000 entidades configurable. Un cursor vencido requiere
bootstrap nuevo conservando intenciones locales. Preparación 7 d no extiende sesión.
B40 debe añadir limpieza de SyncSnapshot vencidos y revisar dimensionamiento.

B29: /sync/events y resultados NO_PROCESADA/persisted documentados en
docs/SYNC_PROTOCOL.md. No consumir fallos de autenticación; operaciones dependientes
de entidades aún inexistentes solo quedan en espera, sin efectos ni auditoría de
negocio hasta revalidar permisos. Hora local debe incluir offset; no autoeditar UUID.

B30: login/me incluyen session_expires_at; Device incluye preparation_valid.
Expiración absoluta evita prolongar sesión al registrar dispositivo. Trabajo previo
se reenvía tras login de la misma cuenta con permisos actuales, conservando UUID.

B31: contrato/configuración en docs/PUSH.md. Suscribirse asocia dispositivo a sesión;
logout acepta X-Device-ID y desactiva ese dispositivo, baja de cuenta desactiva todos.
VAPID deshabilitado por defecto; claves persistentes fuera de Git. Sin envíos reales.
pywebpush 2.5.0 fijado con dependencias/hashes. scripts/compile_locked.py reutiliza
SHA-256 del índice Simple, con cálculo normal si falta; descarga local validada
contra el lock. Evita descargar cientos de ruedas ajenas solo para recalcular hashes.

B32: cada aviso nuevo crea un PushDelivery por suscripción activa dentro de la
transacción de negocio. Replay no reencola ni crea envíos retroactivos para nuevas
suscripciones. Payload genérico con notification_id/tag y url=/; abrir requiere
consultar la bandeja autenticada y estado actual. B33 habilita el procesamiento.

B33: worker/diagnostico en docs/PUSH.md. Entrega externa al menos una vez;
ACEPTADO_PROVEEDOR no prueba entrega/lectura. Sin envio real a telefonos.
