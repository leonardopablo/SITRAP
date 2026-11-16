# Cuyes · Etapa 1

Implementación independiente del piloto de leche. No habilita ventas, kits,
reservas, cobros, PIN, reparto, Conductor ni maíz. Las especificaciones revisión 3
siguen gobernando leche; este documento describe la ampliación de inventario.

## Puesta en marcha local

Los comandos del README siguen vigentes. PostgreSQL real, sesiones Django/CSRF,
API `/api/v1` sin barra final, zona `America/Lima`, PWA React/Vite e IndexedDB.
Abrir la PWA por Vite, no por el puerto Django.

```powershell
.\scripts\local-postgres.ps1 Start -Port 55433
.\.venv\Scripts\python.exe scripts/backup_local.py
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
# En otra consola, desde frontend:
npm run dev
```

El helper de respaldo rechaza hosts no locales y guarda un dump en
`.local/backups/`, ignorado por Git. No se cargan centros, galpones, pozas,
animales, cuentas ni saldos con las migraciones. Solo se añade el rol GALPONERO.
Las aproximadamente 1.500 cabezas de referencia de cada centro NO son saldos.

### Recorrido desde la interfaz

1. Ingresar como ADMIN. Abrir **Cuyes → Configuración de Cuyes**.
2. Elegir **Habilitación por centro**, seleccionar el registro existente de
   Canchán o Kotosh y guardar con motivo. Si falta realmente un centro, crearlo
   primero en Catálogos; no crear variantes por tildes o Kotosh/Cotosh.
3. Crear los galpones: uno de Canchán y dos de Kotosh, según la validación física.
   Crear pozas con código físico único, capacidad real y propósito.
   Ejemplos de códigos, no datos precargados: CAN-G1-P01, KOT-G1-P01, KOT-G2-P01.
4. En **Cuentas**, crear/seleccionar una cuenta personal y asignarle
   **GALPONERO**, ámbito de ubicación y centro habilitado. Volver a Configuración
   de Cuyes y autorizar **cada galpón** de esa asignación. Tener acceso a Kotosh
   no autoriza automáticamente sus dos galpones. La misma cuenta puede conservar
   PRODUCCION y elegir su espacio en **Cuenta y ajustes → Espacio de trabajo**.
5. Ingresar como GALPONERO: una cuenta con solo ese rol entra directamente a
   Cuyes. Seleccionar galpón/poza. Elegir **Apertura por conteo físico** y cargar
   cada categoría/calidad observada. Si se desconoce calidad, usar SIN_CLASIFICAR;
   si se desconoce nacimiento, dejar fechas vacías. Separar grupos de distinta
   procedencia/edad con **Preparar este grupo y añadir otro**. Enviar una sola
   apertura completa por poza. Puede abrirse vacía con cantidades cero.
6. Ir a **Sincronización → Preparar dispositivo** con conexión. Regresar a Cuyes.
7. Registrar **Nacimiento**, seleccionando el grupo reproductor con hembras:
   vivos incrementan lactantes en un nuevo lote de edad conocida; natimortos
   quedan como estadística. Después registrar **Mortalidad**, eligiendo
   ocupación, categoría, calidad, cantidad y causa probable o «desconocida».
8. Para **Destete y sexaje**, seleccionar la ocupación de lactantes, calidad de
   origen y repartir cantidades entre recrías compatibles: machos/hembras,
   calidad A/B. Añadir líneas para distintos destinos. Se aplica todo o nada.
9. Usar **Traslado inmediato** dentro del mismo centro y con acceso a ambos
   galpones. Entre centros usar **Despacho a otro centro**. El galponero receptor
   verá el tránsito y pulsará **Confirmar recepción física**. El origen no puede
   recibir por él. Si el destino no está disponible, redirigir con motivo:
   el receptor solo dentro de su centro y a sus pozas; ADMIN puede cambiar centro.
10. Registrar el **Conteo mensual** de cada lote/categoría/calidad al corte.
    Las combinaciones omitidas significan cero observado: revisar antes de enviar.
    No cambia el inventario. ADMIN ve esperado, observado y diferencia y puede
    aprobar el ajuste o rechazar con motivo. Un ajuste incoherente permanece
    pendiente, sin cambiar ni borrar el conteo original.
11. Elegir **Cerrar parte diario** incluso con cero novedades. La PWA sincroniza
    primero las intenciones de esa fecha/galpón y bloquea si quedan pendientes,
    rechazos o intenciones de galpones ya revocados que no pueda identificar.
    Una novedad tardía queda rechazada hasta una reapertura administrativa.
    Tras revisar un rechazo, se puede reconocer localmente con motivo, sin
    aplicarlo ni borrar su intención; si el hecho debe registrarse, crear una
    nueva intención después de resolver su causa. El reconocimiento no es
    aprobación de ajuste ni autorización para saltarse una reapertura.
12. ADMIN puede **Reabrir con motivo**, revisar diferencias, registrar
    compensaciones de movimientos y volver a cerrar. El historial permanece.

El tablero se filtra por centro, galpón o poza y mes; muestra población confirmada,
tránsito, capacidades, cierres, conteos, indicadores y hora de actualización.
Un propietario que administra usa su cuenta ADMIN. Los servicios de lectura y
los permisos están separados para añadir después un rol de consulta, no creado aún.

## Reglas de manejo

- Maternidad admite machos, hembras y lactantes; nacimientos requieren un grupo
  con hembras presentes. Se crea un lote hijo por nacimiento, con fecha conocida.
- Recría Machos solo MACHO; Recría Hembras solo HEMBRA. El destete exige A/B.
- Acabado admite machos y hembras destetados de cualquier calidad, no lactantes.
  El propósito no habilita ventas ni produce reclasificaciones.
- Enfermería admite las tres categorías y cualquier calidad para permitir el
  manejo sanitario de madres/crías; no cambia automáticamente categoría/calidad.
- Cambiar a calidad C por reclasificación exige ADMIN. Registrar una calidad C
  ya observada en la apertura no es una reclasificación.
- El destete conserva padre y ocupación madre y crea lote hijo con apertura de
  recría y referencia de nacimiento heredada. Un traslado conserva el lote;
  mezclar grupos no los fusiona ni borra sus identidades.
- Las ocupaciones se cierran al quedar en cero. Se puede consultar el vaciado
  completo para manejo «todo dentro, todo fuera». Un nuevo ingreso conserva su
  lote y abre otra ocupación cuando corresponde.
- Edad: intervalo de días desde nacimiento conocido; sin referencia se presenta
  «edad desconocida». Recría: días desde apertura del lote de destete.
  Antigüedad reproductiva: días desde instalación, nunca desde una edad supuesta.

## Kardex, fechas y concurrencia

Tablas propias en `apps/cuyes`: Shed, Pen, ShedGrant, CuyLot, Occupation, Balance,
Movement, LedgerLine, PhysicalCount/CountDetail, DailyReport/DailyRevision,
AlertPolicy/Alert y Transfer.

El Kardex y sus etiquetas originales son la referencia. Cada línea guarda código
de poza, galpón y centro, lote, procedencia y fechas de edad; categoría/calidad y
delta están en la línea. Cambiar etiquetas actuales no reescribe el pasado.
Movement también conserva autor, motivo, intención y fecha operativa; el servidor
registra su propia hora. Las cantidades son enteros.

Todos los efectos y auditoría se aplican en una transacción. Se bloquean galpones
y después pozas en orden UUID consistente: capacidad se protege sobre la poza
completa, no solo sobre un lote. El cierre toma el mismo bloqueo de galpón, por
lo que compite correctamente con novedades de otra cuenta. Recepción/redirección
serializan primero el traslado. Las recepciones consumen una sola vez el tránsito.

Reintentos pasan por `SyncOperation`, hash canónico, dispositivo y cuenta:
no modificar UUID/payload para «forzar» una intención rechazada. Los replays
vuelven a comprobar los permisos. Los triggers PostgreSQL impiden UPDATE/DELETE
de movimientos, líneas, lotes, detalles de conteo y revisiones de parte.
No prometen protección frente al propietario de la base con permisos DDL.

Las correcciones son compensaciones, no edición del Kardex. ADMIN puede compensar
nacimiento, mortalidad, destete, traslado inmediato y reclasificación, una sola vez
por original, con motivo y validaciones de saldo/capacidad. Aperturas y conteos se
corrigen con conciliación; tránsito usa sus etapas específicas. Una topología de
ocupaciones que no permite compensar coherentemente exige revisión.

Capacidad: destetes y traslados se rechazan si la exceden; nacimientos, aperturas y
hechos observados por conteo se conservan y generan alerta. Un cambio de propósito
se rechaza si es incompatible con animales presentes. Desactivar no borra historia.

### Corte físico

El conteo captura esperado por ocupación/categoría/calidad al corte y observados.
El esperado se reconstruye del Kardex hasta la fecha de corte, con los hechos
que ya estaban registrados al crear el conteo. El instante de registro separa
movimientos posteriores del mismo día. No se permiten novedades retroactivas de
fecha anterior a un conteo ya capturado: requieren revisión.

La aprobación aplica **observado − esperado capturado**, no sustituye el saldo
actual por el observado. Conserva por tanto los movimientos posteriores. Se valida
que no queden saldos actuales/históricos negativos. Solo un conteo periódico
pendiente por poza evita superponer ajustes de cortes aún no revisados.

## Indicadores y alertas

- Nacidos vivos y natimortos: por grupo/poza de maternidad. Las compensaciones
  descuentan las estadísticas en su período de registro operativo.
- Mortalidad: salidas por muerte, netas de compensación.
- Destetados: lactantes que salen por destete, atribuidos a la poza madre,
  no a las recrías receptoras.
- Promedio de hembras: suma de hembras al cierre de cada día / días del período,
  reconstruida de todas las entradas y salidas por categoría HEMBRA.
- Destetados/hembra: destetados / promedio anterior. Se requiere apertura física
  anterior o igual al inicio del período y promedio positivo. Si falta esa
  cobertura histórica o denominador, se informa «datos insuficientes».
  No se extrapolan hembras de un conteo posterior al inicio.

Al habilitar un centro se crea una política con **13 meses** y umbral mensual
**1,00 destetados/hembra**, ambos editables. Son parámetros de revisión, no
diagnóstico ni clasificación automática. **Evaluar alertas** comprueba antigüedad
desde instalación y rendimiento del último mes calendario completo.

La alerta de antigüedad se deduplica por lote; rendimiento por poza/mes;
sobrecapacidad por poza. Resolver exige motivo y conserva la alerta. Repetir la
evaluación no reabre ni duplica el mismo caso resuelto. Las diferencias y alertas
generan avisos persistentes a ADMIN en la bandeja existente, con outbox push
opcional. Abrirlos no aplica un ajuste. La evaluación por antigüedad/rendimiento
es explícita desde el tablero; no se instala un planificador de infraestructura.

## API y sincronización

Prefijo `/api/v1/cuyes/`:

| Ruta | Uso |
|---|---|
| `config` GET/POST | Configuración ADMIN; reutiliza Location y CUYES/UN/CenterProduct |
| `sheds`, `pens`, `pens/{uuid}`, `balances` GET | Galpones/pozas/saldos autorizados |
| `destinations` GET | Opciones mínimas de despacho, sin saldo de otros ámbitos |
| `history`, `kardex` GET | Kardex paginado con etiquetas originales |
| `transfers`, `counts`, `daily-reports`, `alerts` GET | Consultas paginadas |
| `dashboard` GET | Resumen filtrado e indicadores |
| `commands` POST | Sobre de comando tipado con payload estricto |

Comandos: CUY_OPEN, CUY_BIRTH, CUY_DEATH, CUY_WEAN, CUY_MOVE, CUY_DISPATCH,
CUY_RECEIVE, CUY_REDIRECT, CUY_RECLASS, CUY_COUNT, CUY_REVIEW, CUY_CLOSE,
CUY_REOPEN, CUY_RESOLVE, CUY_ALERTS y CUY_COMPENSATE.
OpenAPI es el contrato ejecutable de sus campos.

Las opciones intercentro solo muestran pozas habilitadas con galponero receptor
vigente. Mostrar la opción de despacho no concede lectura de sus saldos ni permiso
de recepción. Traslado inmediato/destete requieren autorización de ambos extremos.

`CUY_BIRTH` y `CUY_DEATH` usan `/sync/events` y la misma cola durable por cuenta.
Solo pueden capturarse sobre ocupaciones descargadas y preparación vigente;
UUID, fecha e intención sobreviven a reintentos. Las otras acciones son online.
Los errores de saldo, permisos o cierre quedan para revisión, no se corrigen solos.

Bootstrap/changes añade `cuy_shed` y `cuy_pen`, únicamente de galpones autorizados.
El hash de ámbito incluye grants, habilitación y galpones; cambios paginados
incompletos se invalidan al cambiar acceso. La siguiente descarga entrega
tombstones de datos revocados, sin borrar las intenciones de la cuenta.
El tablero nunca suma la cola de otro teléfono.

## Migraciones y verificación

- accounts 0004: catálogo y restricción PostgreSQL para GALPONERO.
- accounts 0005: semilla del rol, sin cuentas/asignaciones.
- cuyes 0001: tablas y restricciones iniciales.
- cuyes 0002: historial append-only.
- cuyes 0003: índices y restricciones adicionales de Kardex/tránsito/cierre.

No revertir estas migraciones para cambiar de rama si ya se registraron hechos
de cuyes: conservar el esquema aditivo y el respaldo. No hay despliegue.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .local/pytest-temp
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn
# frontend:
npm run api:generate
npm test
npm run build
npm run test:e2e
```

Prueba opt-in de navegador móvil **contra Django y PostgreSQL reales**, sin mocks:

```powershell
$env:SITRAP_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_cuyes_browser.py -q --basetemp .local/pytest-browser
Remove-Item Env:SITRAP_BROWSER_TESTS
```

Usa la base temporal de pytest, live_server y Vite en 4181. Crea únicamente
fixtures de prueba aisladas; no modifica cuentas ni saldos locales. Playwright
requiere su navegador Chromium instalado. El resto de E2E del proyecto sigue
usando el mock explícito; no confundir sus resultados con este recorrido real.
La instalación PWA, Web Push y desconexiones prolongadas en Android físico
siguen requiriendo validación de campo.
