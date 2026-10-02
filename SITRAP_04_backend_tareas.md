# SITRAP — backend, contratos y desarrollo por tareas

**Revisión 3 · 2 de octubre de 2026.**  
[General](SITRAP_01_descripcion_general.md) · [Datos/UML](SITRAP_02_arquitectura_base_datos.md) · [Frontend](SITRAP_03_frontend_tareas.md).

## 1. Arquitectura y alcance

Monolito modular con Python, Django, Django REST Framework y PostgreSQL. PWA y escritorio utilizan la misma API `/api/v1`. Servicios de dominio centralizan permisos, estados, cantidades, idempotencia y auditoría. La API directa y el procesador offline invocan esos mismos servicios.

| Componente | Tecnología y propósito |
|---|---|
| API | Django + DRF; OpenAPI con drf-spectacular. |
| Persistencia | PostgreSQL, Decimal, transacciones y bloqueos de filas. |
| Acceso | Sesiones Django del lado servidor y CSRF, mismo origen HTTPS. |
| Informes | HTML controlado por servidor + WeasyPrint para PDF. |
| Notificación al teléfono | Web Push con VAPID; biblioteca Python compatible como pywebpush, fijada y verificada en B31. |
| Procesamiento push | Worker como proceso separado del mismo proyecto, comando Django; cola durable `envio_push` en PostgreSQL. |
| Pruebas | pytest/pytest-django; PostgreSQL real en concurrencia e integración. |
| Operación | Web y worker desplegados por separado; secretos en configuración protegida; logs sin contraseñas ni claves push. |

No hacen falta microservicios, Redis, Celery o WebSocket en este piloto. El worker sí es necesario para reintentos de push sin bloquear peticiones. Polling en la app abierta mantiene listas actualizadas; Web Push avisa fuera de la app. Ambos parten de hechos persistidos, no de un mensaje enviado directamente entre teléfonos.

Estructura propuesta: `apps/accounts`, `catalog`, `production`, `milk`, `traceability`, `sync`, `notifications`, `reports`, `audit`, más `config` y `tests`. Ventas, tesorería, inventario físico, pérdidas, cuyes e IA quedan fuera. No añadir endpoints de incidencias o recepción con diferencia.

Fijar versiones compatibles y con soporte al comenzar, usando archivos de bloqueo. El modelo y sus estados se definen en el documento 02; este documento es fuente única del catálogo de comandos (§5) y eventos de notificación (§6). OpenAPI será el contrato ejecutable al implementar.

## 2. Sesiones, permisos y funcionamiento offline

- Una página de login. `GET /auth/me` devuelve cuenta, asignaciones, ubicaciones y capacidades; no hay registro público.
- Login protegido contra CSRF y fuerza bruta. Cookie de sesión HttpOnly, Secure y SameSite=Lax; CSRF Secure y `X-CSRFToken` en mutaciones. No guardar contraseñas o tokens de sesión en IndexedDB/localStorage.
- Mismo origen en producción: `/` frontend, `/api/v1/` backend. Proxy Vite durante desarrollo. No requiere CORS en producción. Si se adoptan dominios distintos, revisar orígenes explícitos, cookies y `CSRF_TRUSTED_ORIGINS`; nunca `*` con credenciales ni desactivar CSRF.
- Duración inicial propuesta: sesión de 12 horas, preparación offline de 7 días desde validación online, configurables y a validar en campo. La preparación local no prolonga la sesión central ni garantiza autenticación offline.
- Captura offline provisional en dispositivo personal preparado. El servidor vuelve a comprobar usuario activo y permisos actuales al sincronizar. Al vencer preparación, solo notas locales; conservar operaciones anteriores.
- Sesión vencida: `SESSION_EXPIRED`; mantener cola y pedir acceso de la misma cuenta. Renovar CSRF y reenviar UUID originales. Otra cuenta no hereda ni envía esos registros.
- Logout online desactiva la suscripción push del dispositivo y revoca sesión antes de limpiar datos locales autorizados. Con pendientes, ofrecer sincronizar antes o bloquear conservándolos para la misma cuenta; nunca perderlos silenciosamente.
- Logout offline bloquea la app localmente y desuscribe push localmente cuando sea posible. Al recuperar conexión, intentar revocación central antes de nuevas tareas. Hasta entonces no afirmar que la sesión o los push centrales ya fueron revocados. El payload genérico reduce exposición en un aviso tardío.
- Desactivar cuenta o permiso bloquea operaciones nuevas y sincronizadas. Desactivar cuenta también desactiva suscripciones. ADMIN puede designar reemplazos para trabajo nuevo, no firmar por otra persona.

## 3. Contrato transversal e integridad

Lecturas paginadas y limitadas por permisos; aceptar rangos de fechas acotados. Devolver `lock_version`, estado, referencias documentales y capacidades actuales. Importes/cantidades decimales como strings; fechas operativas en America/Lima y timestamps ISO 8601 con zona.

Toda mutación de dominio —incluido guardar borrador— usa el sobre siguiente. Los endpoints directos fijan `type` según su acción; `/sync/events` lo recibe explícitamente.

```json
{
  "event_id": "UUID estable para esta intención",
  "device_id": "UUID del dispositivo registrado",
  "type": "TRANSFER_PICKUP",
  "entity_id": "UUID del traslado",
  "occurred_at": "2026-10-02T08:00:00-05:00",
  "expected_version": 4,
  "depends_on": [],
  "payload": {"version_id": "UUID del documento que vio Lolo"}
}
```

El glosario de `lock_version`, `expected_version`, `version_id` y `numero` está en 02 §2. Nuevas entidades tienen UUID generado por cliente; no llevan expected_version. El servidor obtiene actor de la sesión. No aceptar un actor indicado libremente en payload.

Registro idempotente, cambio de negocio, auditoría, aviso interno y outbox push se confirman atómicamente. UUID repetido con la misma cuenta, dispositivo, tipo y contenido devuelve el resultado anterior; contenido distinto da `IDEMPOTENCY_CONFLICT`. Hashear representación canónica que incluya dependencias. No reinterpretar un evento rechazado mutando su payload: crear otro UUID tras revisión del usuario.

Respuesta por operación: `event_id`, `status`, `entity_id`, `lock_version`, `result`, `server_received_at`. Errores: `code`, `message`, `field_errors`, `retryable`. Códigos mínimos: `SESSION_EXPIRED`, `CSRF_FAILED`, `PERMISSION_DENIED`, `VALIDATION_ERROR`, `VERSION_CONFLICT`, `DEPENDENCY_MISSING`, `DEPENDENCY_REJECTED`, `IDEMPOTENCY_CONFLICT`, `CORRECTION_PENDING`, `INVALID_STATE`, `ALLOCATION_EXCEEDED`.

`401` sesión ausente/vencida; `403` autorización o CSRF con código diferenciable; `409` versión/estado/idempotencia; `422` validación. Normalizar DRF para no depender de su respuesta predeterminada de autenticación. Dependencia pendiente devuelve acuse 202 o estado individual equivalente. Batch válido retorna resultados individuales incluso si unas operaciones fallan; sobre mal formado se rechaza antes de procesar.

Confirmar recogida o recepción no recibe litros editables: copia líneas de `version_id` vigente. Bajo bloqueo, verifica que no exista la etapa física en ninguna versión anterior. La interfaz nunca puede crear una segunda recogida al cambiar un UUID o una revisión documental.

Orden estable de bloqueos entre todos los servicios: producciones afectadas ordenadas por UUID → lotes → traslados → solicitudes de corrección. Determinar relaciones, adquirir bloqueos y releer antes de actuar; ninguna ruta adquiere estos recursos en orden inverso. Rectificación y publicación usan los mismos bloqueos de producción/lote. Lecturas de informes usan una fotografía consistente durante el cálculo.

## 4. API y matriz de acceso

Prefijo `/api/v1`. En las tablas, P = PRODUCCION del centro, T = TRANSPORTE asignado, R = RECEPCION asignada, A = ADMIN. El permiso requiere cuenta activa y ámbito vigente; un rol no habilita todos los centros. ADMIN consulta globalmente y administra, pero no obtiene por ello facultad de confirmar recogidas, recepciones o aprobar correcciones. Una cuenta con varios roles actúa bajo el permiso operativo explícito correspondiente.

| Endpoint / acción | Acceso y condición |
|---|---|
| GET `/auth/csrf`; POST `/auth/login` | Público para iniciar sesión; login con CSRF. |
| GET `/auth/me`; POST `/auth/logout`, `/auth/change-password` | Propia cuenta. Contraseña temporal exige cambio; renovar sesión y revocar las otras. |
| GET/POST `/users`; PATCH `/users/{id}`; POST `/users/{id}/reset-password` | A. Desactivar no borra historia. |
| GET/POST `/role-assignments`; PATCH `/role-assignments/{id}` | A; validar GLOBAL/UBICACION según 02. |
| GET `/locations`, `/products`, `/center-products`, `/presentations`, `/species`, `/turns` | Usuarios autenticados, solo catálogo necesario a sus ámbitos. A global. |
| POST/PATCH de esos catálogos | A. Productos habilitados por centro, sin cantidad en catálogo. |
| GET `/assignment-options?origin_id=…&destination_id=…` | P del origen o A. Conductores, destinos y receptores asignables; id/nombre mínimos y defaults si existen. No devuelve contraseñas, teléfonos ni todo `/users`. |
| GET `/animals`; GET `/animals/{id}` | P de su centro; A global. |
| POST `/animals`; PATCH `/animals/{id}`; GET/POST `/animals/{id}/stays` | P en su centro o A; movimientos entre centros solo A. Auditar y no superponer estancias. |
| GET `/milkings`; GET `/milkings/{id}` | P del centro, A. T/R consultan solo el resumen de procedencia de sus entregas, no todo el detalle animal. |
| POST `/milkings`; PATCH `/milkings/{id}`; POST `/milkings/{id}/confirm`, `/rectify`, `/void` | P. PATCH solo borrador; rectificar litros versiona; anular aplica restricciones de 02. |
| GET `/lots`; GET `/lots/{id}` | P del centro, T/R vinculados al traslado, A. |
| GET `/transfers`; GET `/transfers/{id}`; GET `/transfers/{id}/timeline` | P origen, T/R asignados o participantes históricos dentro del ámbito vigente, A global. |
| POST `/transfers`; PATCH `/transfers/{id}` | P; borrador con líneas anidadas atómicas. |
| POST `/transfers/{id}/send`, `/revise`, `/cancel` | P; enviar borrador, revisar/cancelar antes de recogida. |
| POST `/transfers/{id}/pickup` | T asignado; versión vigente y estado PENDIENTE_RECOGIDA. |
| POST `/transfers/{id}/receive` | R asignado; EN_CAMINO sin corrección pendiente; recepción física. |
| POST `/transfers/{id}/reassign-receiver` | A, solo EN_CAMINO sin recepción y sin ninguna solicitud de corrección histórica; motivo obligatorio. |
| POST `/transfers/{id}/corrections` | P del origen; EN_CAMINO/RECIBIDO, propuesta concreta y motivo. |
| GET `/corrections`; GET `/corrections/{id}` | P origen, aprobadores fijados, A. Devuelve propuesta, antes/después, decisiones y pendientes. |
| POST `/corrections/{id}/accept`, `/reject` | Exclusivamente cada uno de los dos aprobadores fijados; permiso actual T/R. A no puede sustituirlos. |
| POST `/corrections/{id}/withdraw` | Solicitante P, aún PENDIENTE. |
| POST `/devices`; GET `/devices/current` | Propia cuenta/dispositivo. Registrar es idempotente por UUID; requiere conexión. |
| GET `/sync/bootstrap`, `/sync/changes`; POST `/sync/events` | Cuenta/dispositivo propios; cada lectura y cada comando revalida alcance. |
| GET `/notifications`; POST `/notifications/{id}/read` | Solo destinatario. Marcar leído es idempotente, no confirma leche. |
| GET `/push/config`; GET/POST `/push/subscriptions`; DELETE `/push/subscriptions/{id}` | Propia cuenta y dispositivo. Config devuelve clave VAPID pública y capacidad; nunca privada. |
| GET `/metrics/milk` | P del centro, A; litros por vaca/fecha/turno, promedio y cobertura de registros. |
| GET `/metrics/transfers` | P origen, T propio, R propio/destino autorizado, A global. Separar recogido y recibido. |
| GET `/reports/production.pdf` | P centro, A. |
| GET `/reports/transfers.pdf` | T propio, P origen, A. |
| GET `/reports/receptions.pdf` | R propio/destino autorizado, A. |
| GET `/reports/overview.pdf` | A global, filtros de centro/producto/período. |

Cambios de catálogos/cuentas y reasignación requieren conexión. Reasignar receptor crea revisión auditada conservando conductor y cantidades; no copia su conformidad anterior. El nuevo receptor confirma su recepción, y el anterior pierde capacidad de recibir. Si hubo cualquier solicitud de corrección, la reasignación se bloquea en este MVP.

Las rutas `/{id}/rectify`, `/void` de la tabla son subrutas de `/milkings/{id}`; no endpoints globales. El detalle y los listados deben aplicar el mismo filtro de permisos, incluidos PDF y cambios offline. Ningún ID recibido acredita por sí solo autorización.

## 5. Sincronización: fuente única de comandos

### Catálogo operativo

Estas operaciones usan el mismo servicio en API directa y `/sync/events`. Los payloads listan campos funcionales, además del sobre §3. Uuid/versiones exactos se tiparán en OpenAPI. Operaciones de administración, catálogos y suscripciones son exclusivamente online y utilizan idempotencia en su servicio o semántica idempotente propia; no se introducen como comandos offline implícitos.

| Tipo | Payload funcional / condición | Captura offline |
|---|---|---|
| `MILKING_CREATE` | centro, fecha, turno, detalles iniciales; UUID del ordeño/producción/version inicial predeterminados | Sí, centro preparado. |
| `MILKING_UPDATE` | fecha/turno válidos, detalle completo de borrador; expected_version | Sí. |
| `MILKING_CONFIRM` | versión del borrador; UUID de lote a crear | Sí, tras creación/ediciones dependientes. |
| `MILKING_RECTIFY` | detalle completo por vaca y motivo; expected_version | No, requiere comprobar asignaciones actuales. |
| `MILKING_VOID` | motivo, expected_version | No, comprobar vínculos activos. |
| `TRANSFER_CREATE` | UUID versión borrador, lote, presentación, bolsas, destino y participantes | Sí, lote conocido o dependiente del cierre local. |
| `TRANSFER_UPDATE` | documento borrador completo permitido | Sí. |
| `TRANSFER_SEND` | version_id de borrador revisado | Sí; solicitud remota solo tras acuse central. |
| `TRANSFER_REVISE` | cantidades/asignación permitidas, motivo, UUID nueva versión | No, antes de recogida y contra estado actual. |
| `TRANSFER_CANCEL` | motivo | No, antes de recogida. |
| `TRANSFER_PICKUP` | version_id mostrado; sin cantidad libre | Sí, solicitud previamente descargada. |
| `TRANSFER_RECEIVE` | version_id mostrado; sin cantidad libre | Sí, entrega EN_CAMINO previamente descargada. |
| `CORRECTION_CREATE` | nueva cantidad, motivo, UUID solicitud y versión propuesta; expected_version del traslado | No. |
| `CORRECTION_ACCEPT` | version_id de propuesta; expected_version de solicitud | Sí, propuesta descargada. |
| `CORRECTION_REJECT` | version_id de propuesta, motivo; expected_version de solicitud | Sí, propuesta descargada. |
| `CORRECTION_WITHDRAW` | motivo; expected_version de solicitud | No. |

`POST /sync/events` rechaza tipos desconocidos. Comandos marcados No requieren procesamiento directo online; no deben almacenarse como una nueva intención offline. Un reintento de transporte de una petición online conserva su UUID y no equivale a habilitar su creación offline.

### Orden, conflictos y dependencias

1. Eventos locales se guardan en IndexedDB antes de mostrar “Guardado en este teléfono”. Cada intención tiene UUID estable y dependencias explícitas.
2. Crear ordeño → actualizarlo → confirmarlo → preparar entrega → enviarla. Referencias UUID permiten ordenar sin que el lote exista todavía en servidor. Una dependencia ausente conserva ESPERA_DEPENDENCIA; una rechazada propaga DEPENDENCY_REJECTED.
3. Para operaciones consecutivas sobre un mismo agregado local, el cliente mantiene la versión esperada resultante de cada comando exitoso y registra dependencia. Si otro dispositivo cambia el agregado, se detiene la cadena ante conflicto; nunca reescribir expected_version a ciegas.
4. Procesar en orden topológico, detectando ciclos y límites de lote/tamaño. Reintentar operaciones en espera cuando llegue su padre; una espera vieja se muestra al usuario y no se descarta silenciosamente. No aceptar dependencias ajenas sin relación autorizada.
5. Si una primera aprobación cambia la solicitud, una segunda offline puede recibir VERSION_CONFLICT. Recuperar propuesta/decisiones: si sigue siendo la misma propuesta inmutable PENDIENTE, mostrar el estado actualizado y solicitar reintento explícito; no autoaprobar una nueva versión.
6. Error de autenticación/CSRF no consume la intención como rechazo de negocio. Renovar sesión/CSRF, reintentar. Conflicto o rechazo definitivo exige revisión humana y UUID nuevo si decide otro comando.
7. Lolo no puede recibir automáticamente una solicitud que solo existe en el teléfono de Vilma. Deben sincronizar antes de confirmar en otro teléfono. Si ambos no pueden, nota provisional y vinculación manual posterior; no declarar una conformidad remota inexistente ni inventar lotes. Tampoco María ve un cambio de Lolo aún no sincronizado.

Bootstrap: permisos, catálogos habilitados, opciones asignables, animales necesarios para P, lotes autorizados, entregas abiertas de cualquier fecha, versiones/conformidades, correcciones pertinentes y bandeja. Historial por defecto 30 días paginado. Cambios con cursor estable y tombstones de desactivación/revocación; no omitir bajas ni seguir mostrando datos cuyo permiso ya se retiró. Un cursor expirado obliga a nuevo bootstrap sin perder outbox local.

Sincronizar en primer plano al abrir, recuperar foco/conexión y pulsar “Sincronizar”. Background Sync es una mejora opcional, no requisito para operar. El caché no reemplaza PostgreSQL ni garantiza que un registro local sobreviva al borrado de datos del teléfono.

## 6. Notificaciones: fuente única de eventos

Cada evento nace de una transacción de negocio APLICADA. Se deduplican destinatarios. Un registro interno por destinatario y un envío por suscripción activa; ningún registro local no sincronizado genera aviso remoto.

| Tipo de notificación | Hecho | Destinatarios |
|---|---|---|
| `PICKUP_REQUESTED` | Entrega enviada | Conductor asignado. |
| `PICKUP_REQUEST_UPDATED` | Revisión antes de recogida | Conductor actual; si cambió, aviso informativo al anterior. |
| `TRANSFER_CANCELLED` | Cancelación de solicitud publicada | Conductor que la tenía asignada. |
| `RECEPTION_PENDING` | Recogida confirmada | Receptor asignado. |
| `RECEIVER_REASSIGNED` | Reasignación permitida antes de recepción | Nuevo receptor, anterior, conductor y producción. |
| `RECEPTION_CONFIRMED` | Recepción física confirmada | Emisor y conductor. |
| `CORRECTION_REQUESTED` | Propuesta creada | Los dos aprobadores fijados. |
| `CORRECTION_PROGRESS` | Primera aceptación | Solicitante y otro aprobador. |
| `CORRECTION_APPLIED` | Segunda aceptación y aplicación atómica | Solicitante y ambos aprobadores. |
| `CORRECTION_REJECTED` | Rechazo y cierre | Solicitante y ambos aprobadores. |
| `CORRECTION_WITHDRAWN` | Retiro por solicitante | Ambos aprobadores. |

Cuando un cambio ya invalidó una acción, el aviso sigue como historia pero el detalle devuelve estado/capacidades actuales. Aviso leído no cambia pendiente operativo. No crear nueva recepción pendiente al aprobar corrección: la entrega conserva su estado, y su tarjeta muestra la cantidad vigente.

Push usa HTTPS, Service Worker y suscripción explícita tras gesto del usuario. El backend almacena endpoint y claves de suscripción para envío, protegidos como datos sensibles; VAPID privada solo en servidor. Validar formato, HTTPS y destinos de proveedores admitidos para evitar URLs arbitrarias/SSRF; no seguir redirecciones a redes internas. Configuración y pruebas de compatibilidad en los Android del piloto antes de producción.

Payload genérico: `notification_id`, `type`, ruta interna construida/validada por la aplicación y texto como “Tienes una entrega pendiente en SITRAP”. No incluir litros, nombres u otros detalles en pantalla bloqueada por defecto. Pulsar abre la app; recuperar sesión y recurso antes de habilitar acciones. No aceptar una entrega desde un botón de notificación del sistema en el MVP.

Worker reclama filas mediante lease con bloqueo y skip_locked; hace la llamada externa fuera de la transacción larga; registra resultado. Respuesta 404/410 desactiva suscripción. Errores temporales reintentan con espera creciente y límite; otros errores quedan FALLIDO para diagnóstico. Validar suscripción/cuenta activa justo antes de enviar. Un fallo push no revierte operación ni notificación interna.

Estados y restricciones de `notificacion`, `suscripcion_push`, `envio_push` están en 02 §11. Recuperar leases vencidos. `notificacion.id` como tag estable evita acumulación innecesaria; no prometer exactamente una visualización. Aceptación por proveedor no prueba entrega ni lectura. Sin permiso, red o compatibilidad: bandeja e historial siguen funcionando.

## 7. Informes y análisis de producción

Filtrar por fecha/centro/producto según alcance, con fecha de corte y zona visibles. PDF incluye responsables reales, cantidades vigentes, anotación de correcciones y referencia al historial. Registrar autor de exportación y parámetros; no exponer documentos por URL pública predecible. Generar desde una lectura consistente y limitar rango/filas; trabajo asíncrono para PDF solo si medición lo justifica.

El servidor no sabe cuántas operaciones quedan en un teléfono: el frontend muestra esa advertencia antes de solicitar PDF. El PDF indica que refleja datos sincronizados al corte. Un parámetro opcional informado por cliente no se debe presentar como verificación global de pendientes.

Producción: litros por vaca, total, promedio por día con registro y cantidad de días registrados; distinguir cero de ausencia. Comparar períodos equivalentes; no tratar más litros como rentabilidad sin alimento/costos ni inferir lactancia no registrada. Traslados: métricas separadas de recogido y recibido, sin sumar ambos como producción. Correcciones cambian valor documental vigente, conservando fecha de la etapa física.

## 8. Desarrollo en tareas cortas

**Regla para todas las tareas:** implementar solo su alcance, ejecutar las pruebas pertinentes indicadas, actualizar contrato/documentación y crear un commit en el repositorio GitHub del proyecto por cada funcionalidad terminada. El commit se crea localmente y se publica en la rama de trabajo configurada; no agrupar funcionalidades independientes en un único commit ni hacer push a una rama protegida sin su flujo. Las pruebas acompañan la funcionalidad, no se posponen al final. Cada fila es un incremento; si excede una sesión, dividirla conservando criterio de aceptación y commits separados.

| ID | Entrega acotada | Depende de | Comprobación y commit sugerido |
|---|---|---|---|
| B01 | Proyecto Django/DRF, configuración por entorno y lockfile | — | Arranca y health básico; `chore: iniciar backend`. |
| B02 | PostgreSQL y runner de pruebas/CI | B01 | Migración limpia y test en BD real; `chore: configurar postgres y pruebas`. |
| B03 | Usuario personalizado y roles/ámbitos | B02 | Checks GLOBAL/UBICACION; `feat: modelar acceso`. |
| B04 | Login, CSRF, me, cambio de contraseña y logout | B03 | Sesión, CSRF, expiración; `feat: autenticar usuarios`. |
| B05 | Autorización central y matriz de capacidades | B04 | Negar acceso entre centros e IDs ajenos; `feat: validar ambitos`. |
| B06 | Registro de dispositivos y operaciones idempotentes | B05 | Duplicado, hash diferente, propietario; `feat: registrar operaciones`. |
| B07 | Auditoría append-only y servicios transaccionales base | B06 | Cambio y auditoría atómicos; `feat: auditar cambios`. |
| B08 | API de cuentas, asignaciones y reset temporal | B07 | Solo A, desactivación y cambio obligado; `feat: administrar cuentas`. |
| B09 | Catálogos de centros, productos y centro_producto | B07 | Alta/desactivación autorizada, no stock; `feat: habilitar productos por centro`. |
| B10 | Unidades, presentaciones, especies y turnos | B09 | Compatibilidad y bolsa indivisible; `feat: completar catalogos`. |
| B11 | Conductores/destinos/receptores asignables | B08, B10 | Datos mínimos, opciones por ámbito; `feat: consultar asignaciones posibles`. |
| B12 | Animales y estancias | B10 | Sin superposición, centro válido; `feat: registrar vacas`. |
| B13 | Borrador de ordeño y detalle por vaca | B06, B12 | UUID, vacío/cero, edición concurrente; `feat: guardar ordenos`. |
| B14 | Confirmación de ordeño y lote único | B13 | Suma, una confirmación, lote una vez; `feat: confirmar produccion`. |
| B15 | Unicidad parcial y servicio interno de anulación/reemplazo, aún sin endpoint público | B14 | Carrera anular/recrear, historial; `feat: preparar anulacion de ordeno`. |
| B16 | Modelo y consulta de traslado/versiones | B14 | Lecturas P/T/R/A y timeline; `feat: consultar entregas`. |
| B17 | Borrador de traslado con línea y participantes | B11, B16 | Transacción y permisos; `feat: preparar entrega`. |
| B18 | Notificación interna y API bandeja/leído | B07 | Destinatario, deduplicación y lectura; `feat: crear bandeja de avisos`. |
| B19 | Publicación y reserva documental de entrega | B17, B18 | Bloqueo lotes, sobreasignación, aviso y anulación prohibida con vínculos; `feat: enviar solicitud`. |
| B20 | Revisión/cancelación antes de recogida | B19 | Obsoleta no confirmable, aviso; `feat: revisar solicitud`. |
| B21 | Confirmación de recogida | B20 | Una etapa, versión exacta, aviso a R; `feat: confirmar recogida`. |
| B22 | Confirmación de recepción | B21 | Sin doble recepción, aviso P/T; `feat: confirmar recepcion`. |
| B23 | Crear solicitud de corrección y consulta | B22 | Dos aprobadores fijos, reserva máxima y bloqueo de nueva recepción; `feat: proponer correccion`. |
| B24 | Aceptar y aplicar tras dos decisiones | B23 | Carrera entre aceptaciones, estado físico intacto; `feat: aprobar correccion`. |
| B25 | Rechazar/retirar propuesta | B24 | Motivo, no aplicar, carrera con aceptar; `feat: cerrar correccion sin cambios`. |
| B26 | Reasignar receptor bajo restricciones | B25 | Ninguna corrección histórica, auditar/avisar; `feat: reasignar recepcion`. |
| B27 | Rectificar litros de producción y exponer anulación con todas sus guardas | B25 | Cubre asignaciones máximas, entregas intactas, anular con vínculos prohibido; `feat: rectificar produccion`. |
| B28 | Bootstrap autorizado y cambios con cursor | B18, B27 | Lotes/abiertas antiguas/correcciones/bajas; `feat: preparar datos offline`. |
| B29 | Ingesta de comandos, dependencias y reintentos | B06, B28 | Orden topológico, padre ausente/rechazado, sin duplicar; `feat: sincronizar operaciones`. |
| B30 | Sesión vencida/revocación durante sincronización | B29 | Cola recuperable, niega privilegios retirados; `fix: proteger sincronizacion`. |
| B31 | Suscripciones Web Push y configuración VAPID | B18 | Propietario, endpoint válido, logout desactiva; `feat: suscribir avisos al telefono`. |
| B32 | Outbox push transaccional para eventos §6 | B25, B26, B31 | Rollback no envía, retry no duplica filas; `feat: encolar notificaciones push`. |
| B33 | Worker push con leases y reintentos | B32 | Caída/reinicio, 404/410, falla proveedor; `feat: entregar avisos push`. |
| B34 | Métricas por vaca con cobertura | B27 | Cero/ausente, revisiones sin duplicar; `feat: analizar produccion`. |
| B35 | Calendario y resumen de traslados/recepciones | B25 | Fecha física, cantidad vigente, sin doble conteo; `feat: resumir entregas`. |
| B36 | PDF de producción | B34 | Permisos, filtros, corte; `feat: exportar produccion`. |
| B37 | PDF de transporte y recepción | B35 | Cada rol, corrección visible; `feat: exportar entregas`. |
| B38 | Resumen y PDF administrativo | B36, B37 | Filtros globales, campos autorizados; `feat: exportar resumen`. |
| B39 | OpenAPI final y datos demo de leche | B30, B33, B38 | Esquema coincide con servicios; `docs: cerrar contrato del piloto`. |
| B40 | Despliegue Azure web/worker y restauración | B39 | HTTPS, worker vivo, backup restaurable; `ops: desplegar piloto`. |

B06 precede todo guardado de borrador. B18 se implementa antes de las primeras solicitudes; B31–B33 añaden el segundo canal sin rehacer los hechos. Las guardas cuya dependencia aparece más tarde se completan antes de habilitar el flujo en piloto; B23 debe actualizar B22 para impedir recepción con propuesta pendiente. B39 verifica integración, no sustituye pruebas por tarea.

## 9. Azure y operación

Propuesta: Azure App Service para web Django y frontend compilado bajo el mismo origen; Azure Database for PostgreSQL Flexible Server; proceso worker continuo separado, por ejemplo Azure Container Apps, ejecutando el mismo paquete/configuración de dominio y conectado a PostgreSQL. Asegurar ejecución continua del worker y salida HTTPS hacia proveedores push. Elegir tamaños/región/costos al desplegar, sin asumir cuotas gratuitas.

El Service Worker y manifiesto se sirven por HTTPS desde el origen de la app. Clave VAPID estable entre despliegues, con procedimiento de rotación; secretos fuera de Git. Migraciones como paso único controlado, no desde todos los procesos simultáneamente. Health web, latido worker, cola retrasada, fallos push y errores de sincronización observables. Backups y prueba de restauración; logs no contienen payloads sensibles ni claves.

La falta de conexión sigue siendo una limitación física: Azure no puede avisar al teléfono antes de que el evento llegue al servidor. En operación se mide tiempo desde registro local, acuse central y confirmación, sin atribuir toda espera a procesamiento del backend.

## 10. Escenarios de aceptación integrados

1. Vilma registra litros por vaca, confirma lote y envía 20 bolsas. Lolo ve 20 L y confirma una vez. María recibe aviso interno/push y confirma al recibir. Los tres historiales y PDF muestran el mismo traslado.
2. Vilma revisa 20 a 19 antes de recogida: Lolo no puede aceptar la versión anterior; refresca y ve la nueva.
3. Tras recogida, Vilma propone 19 en vez de 20. María y Lolo aprueban, en cualquier orden. Segunda aprobación aplica, sin crear otra recogida/recepción; si falta recepción, María aún debe confirmarla.
4. Rechazo o retiro deja 20 vigentes; nadie puede aplicar una propuesta con una sola aprobación ni con ADMIN.
5. Doble toque, repetición de batch o reinicio no duplican producción, lote, conformidad, decisión, aviso ni reserva. Entrega push duplicada no modifica negocio.
6. Login caducado conserva cola; permisos revocados impiden sincronizarla. Propuesta obsoleta pide revisión, sin aceptación automática.
7. Android con permiso recibe aviso fuera de la PWA cuando red/navegador lo permiten. Sin permiso o fallo proveedor, operación e inbox permanecen; no presentar lectura garantizada.
8. Ordeño anulado sin vínculos permite nuevo registro mismo centro/fecha/turno. Datos de prueba no incluyen cuyes, ventas ni inventario.

Fuentes técnicas de referencia (revisadas para esta especificación): [Django sesiones](https://docs.djangoproject.com/en/5.2/topics/http/sessions/), [CSRF](https://docs.djangoproject.com/en/5.2/howto/csrf/), [MDN Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API), [Notificaciones](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API), [PWA offline](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation), [Django/PostgreSQL en Azure](https://learn.microsoft.com/en-us/azure/app-service/tutorial-python-postgresql-app).
