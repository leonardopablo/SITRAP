# Avance backend SITRAP

Rama exclusiva: `agente-backend`. Cuatro documentos revisión 3 leídos íntegramente.
Última tarea terminada: **B11**. Siguiente elegible: **B12**.
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

| B11 | `feat: consultar asignaciones posibles (B11)` (este commit) | 44 pruebas acumuladas; opciones mínimas por origen/destino, defaults solo con una opción, inactivos excluidos y acceso entre centros negado. |

Obtener hash exacto de cada tarea: `git log --oneline --grep='B04'`.
Cada funcionalidad tiene su propio commit; no se publica hasta disponer del remoto.

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

No hay bloqueo funcional actual. No hay remoto Git configurado; URL de GitHub
solicitada al usuario y pendiente. Commits locales disponibles; **ningún push
ni ejecución de CI remoto verificados**. Continuar tareas independientes.

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

**B12–B39 pendientes**. Seguir dependencias exactas de 04 §8:
B05 autorización → B06 dispositivos/idempotencia → B07 auditoría;
después B08–B17 y B18 antes de B19. B23 debe completar la guarda de recepción B22.
B27 requiere B25, B28 requiere B18/B27, B29–B30 sincronización.
B31 requiere B18; B32 requiere B25/B26/B31; B33 worker.
B34–B38 métricas/PDF y B39 contrato/demo solo tras B30/B33/B38.

**B40 pendiente de preparación** después de B39. Dejar configuración e instrucciones
de web/worker, secretos, HTTPS, backup/restauración; el despliegue real queda reservado
hasta integrar frontend. No declarar B40 terminado ni ejecutar Azure.

Para retomar: comprobar rama y status, leer este informe, revisar el último commit,
aplicar migraciones y ejecutar las pruebas pertinentes; continuar en B12, sin rehacer B01–B11.

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
