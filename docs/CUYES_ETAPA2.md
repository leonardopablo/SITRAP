# Cuyes · Etapa 2: ventas y distribución

Ampliación de la Etapa 1 en `apps/cuyes`. No crea un segundo inventario:
Balance/Occupation/CuyLot y el Kardex existente son la única referencia física.
No incorpora maíz, tienda pública, facturación fiscal, pasarelas, faenado ni
devoluciones físicas. El pago, diferencias económicas y su evidencia se verifican
manualmente por ADMIN.

## Configuración y arranque local

Antes de migrar, respaldar la base local. No se cargan saldos, clientes, módulos,
órdenes, cuentas ni precios con las migraciones. Los centros y saldos de Etapa 1
se reutilizan. `main` y el commit de Etapa 1 se conservan por separado.

```powershell
.\scripts\local-postgres.ps1 Start -Port 55433
.\.venv\Scripts\python.exe scripts/backup_local.py
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
# En otra consola, desde frontend:
npm run dev
```

Abrir Vite en `http://localhost:5173`. Sesiones y CSRF siguen usando el proxy de
mismo origen; no se añade CORS ni autenticación por tokens.

Variables opcionales del backend:

| Variable | Valor predeterminado |
|---|---|
| `CUY_SALES_RESERVATION_MINUTES` | 120 minutos desde confirmación en servidor |
| `CUY_SALES_PRIVATE_ROOT` | `<proyecto>/.local/private-sales` |
| `CUY_SALES_MAX_VOUCHER_BYTES` | 5 MiB |
| `CUY_SALES_PIN_ATTEMPTS` | 5 intentos por generación de PIN |

El directorio privado **no debe estar bajo static, un MEDIA_URL público ni un
directorio servido por Vite/nginx**. Copiarlo junto con la base en los respaldos
después de comenzar a registrar comprobantes. La base guarda referencias y hash
SHA-256 del archivo; no se expone una URL pública.

Se aceptan PDF con firma/cierre completos y PNG/JPEG verificados, hasta el límite
configurado. No se admite SVG/HTML. La descarga es attachment, no-store, nosniff y
exige ADMIN en cada petición. La validación de formato no sustituye antivirus ni
la revisión manual de autenticidad del pago.

## Roles y espacios

- **ADMIN:** módulos, solicitudes, disponibilidad del centro, revisión de
  propuestas, pago/comprobante, PIN, conductor, diferencia económica, cancelación
  auditada y retiro posterior en punto de venta.
- **GALPONERO:** confirmar/rechazar/proponer disponibilidad en su centro;
  seleccionar exclusivamente sus galpones; confirmar sus orígenes y registrar
  salida. No valida pagos ni descarga comprobantes.
- **TRANSPORTE:** solo pedidos de modalidad PUNTO, pagados y asignados a su cuenta
  con rol vigente en el centro. No ve recojos directos, precios, pagos ni PIN.
- PRODUCCION y RECEPCION conservan leche. No se amplía RECEPCION para entregar cuyes.

La navegación añade **Ventas** a ADMIN/GALPONERO y **Viajes de cuyes** a TRANSPORTE.
Una cuenta multirrol elige su asignación en Cuenta y ajustes. La API acepta
`workspace=ADMIN|GALPONERO|TRANSPORTE` para aplicar el ámbito y la proyección de
lectura correspondiente. Pedir otro espacio no concede un rol inexistente.
Las firmas físicas requieren el rol operativo vigente incluso si la cuenta
también es ADMIN.

## Cuatro etapas e inventario

1. **Solicitado:** ADMIN guarda cliente mínimo, un centro, modalidad e ítems.
   Se avisa a galponeros. No existe reserva ni descuento.
2. **Confirmación y pago:** GALPONERO confirma toda la demanda en una transacción.
   Reserva IMPAGA con vencimiento. ADMIN verifica y registra el importe exacto,
   moneda, medio, referencia y comprobante. La reserva pasa a PAGADA.
3. **Preparación/ruta:** se seleccionan ocupaciones y cantidades reales, se
   confirman todos los orígenes y, en traslado, el conductor. La salida física
   consume la reserva y genera un único movimiento `SALE_DISPATCH` en el Kardex.
4. **Entregado:** en directo, el PIN confirma salida y entrega juntas. En traslado
   se distingue llegada, permanencia en punto de venta y retiro final del cliente.

Estados internos distinguen SOLICITADO, AJUSTE_PENDIENTE, RESERVADO, PAGADO,
EN_PREPARACION, EN_RUTA, EN_PUNTO, ENTREGADO, RECHAZADO, CANCELADO y VENCIDO.
El estado de presentación indica RESERVA_VENCIDA aunque el job aún no haya
corrido y LISTO_PARA_DESPACHAR cuando están completas las conformidades exigidas.
También muestra faltantes, revisión económica y el estado de pago de la reserva.

### Líneas y módulos

- UNIDAD: sexo/calidad exactos, número de animales y precio por animal.
  Las categorías comerciales autorizadas en esta entrega son MACHO y HEMBRA:
  los lactantes sin sexar deben pasar por destete/sexaje antes de venderse.
- PESO: número entero de animales que se comprometen/retiran, peso acordado en
  **KG con tres decimales**, base VIVO o BENEFICIADO declarada y precio por KG.
  La base declara qué se pesó; no habilita un proceso de faenado ni otro inventario.
- MODULO: cantidad de módulos y precio por módulo. La receta exige ambos sexos,
  cantidades positivas y componentes sin duplicar. Se copia a la línea al
  solicitar: editar el catálogo no reescribe pedidos existentes.
- Importes monetarios: dos decimales, redondeo decimal HALF_UP. Una moneda por
  orden, PEN o USD. No se hacen conversiones de moneda ni de peso.

Para cada módulo, ofertables = mínimo de
`disponible_del_componente // cantidad_por_receta`. Con 8 machos A y 20 hembras A,
la receta 1+3 permite 6 módulos. Confirmar suma la demanda de **todas** las líneas
y recetas: una venta unitaria puede competir con varios tipos de módulo.

Disponibilidad = saldo confirmado elegible − compromisos vigentes. Es
referencial hasta reservar. ADMIN consulta el centro; GALPONERO solo su ámbito
de galpones, descontando conservadoramente los compromisos del centro.

### Ajustes de disponibilidad y peso

GALPONERO puede proponer cantidades por línea antes de reservar. ADMIN acepta o
rechaza la propuesta, con motivo. La orden vuelve a SOLICITADO y requiere una
nueva confirmación física de disponibilidad antes del pago.

ADMIN puede corregir el peso acordado antes de cobrar. Si cambia después del
pago, el pago original queda inmutable y se bloquea el despacho. Una revisión
administrativa registra total anterior/nuevo, diferencia, motivo y tratamiento:
COBRO_ADICIONAL, DEVOLUCION manual o ABSORBIDO. Cobro/devolución de una diferencia
no cero requiere comprobante de esa resolución. No se ejecuta ningún reembolso
externo. No se cambian animales, sexo, calidad ni componentes automáticamente.

## Preparación, conformidades y trazabilidad

FIFO sugiere lotes por fecha de apertura y desempata por UUID de lote/ocupación.
La selección del galponero es la que se guarda, no la sugerencia.

Una línea puede repartirse entre varias ocupaciones y pozas. Las selecciones
vigentes comprometen esos saldos concretos para evitar que dos preparaciones
asignen los mismos animales. Cada galponero reemplaza solo la selección de sus
galpones; se conservan las contribuciones de otros orígenes. Puede liberar
explícitamente su selección con motivo; esto no libera la reserva comercial.

Cada modificación crea otra preparación y ronda. Las conformidades anteriores
permanecen como historia, pero no autorizan la preparación nueva. Si hay varios
galpones, un responsable vigente de cada galpón debe confirmar sus cantidades.
Transporte confirma sobre el mismo identificador de preparación y ronda.

La salida solo procede si coinciden toda la demanda reservada, el detalle por
línea y las existencias de cada ocupación. Se revalidan todos los firmantes,
saldo, centro, categoría/calidad, importe aprobado, reserva pagada y cierre diario
de los galpones. No se permite mezclar centros dentro de una orden.

El despacho conserva ocupación, lote, categoría/calidad, cantidad y snapshot de
centro, galpón, código de poza y referencias de edad al salir. Edad desconocida
continúa siendo desconocida: nunca se inventa. El despacho apunta al movimiento
y cada entrega final apunta permanentemente a su orden y despacho.

**Llegar al punto de venta o retirar después no vuelve a descontar.** Un cambio
de estado no devuelve animales a una poza. No hay devolución física en esta etapa.

## Faltantes y concurrencia

Una muerte, conciliación, reclasificación o traslado de Etapa 1 sigue registrando
el hecho físico incluso si reduce cantidades comprometidas. Al terminar ese
movimiento se detectan reservas/selecciones afectadas, se invalida su ronda, se
marca faltante y se avisa a ADMIN, una vez por episodio.

El despacho vuelve a verificar, aunque no hubiese llegado el aviso. ADMIN debe
resolver el faltante: reposición física registrada, selección alternativa que
cuadre con la orden o cancelación auditada con tratamiento del pago. Revisar el
faltante no inventa animales ni autoriza despachar si la insuficiencia persiste.

Orden de bloqueos compartido con Etapa 1:

1. Cuenta/dispositivo del mecanismo idempotente existente.
2. Bloqueo transaccional de inventario por centro, en orden UUID.
3. Galpones/pozas con el orden usado por el Kardex.
4. Orden y reserva.

Reservar, pagar, vencer, preparar y despachar se serializan con los mismos
recursos del inventario. Despacho y saldo cambian en la misma transacción.
Las restricciones PostgreSQL impiden múltiples reservas activas de la misma
orden, múltiples pagos/despachos y conformidades/entregas duplicadas. Triggers
append-only protegen evidencia, pagos, preparaciones, selecciones, conformidades,
despachos, detalles, entregas y revisiones.

Los comandos SALE_* reutilizan UUID, dispositivo, hash y recibos de SyncOperation.
Una llamada perdida se reintenta con la intención original, no con otro UUID.
Todas las operaciones comerciales son online y se rechazan en `/sync/events`
y en la cola IndexedDB. Se conserva el offline de nacimientos/mortalidad.

## PIN de recojo directo

ADMIN genera un código aleatorio de ocho dígitos, mostrado una sola vez y con
respuesta no-store. Se entrega al cliente por un canal externo. Se almacena
únicamente el hash de contraseña Django, generación y contadores; regenerar
invalida el anterior, incluso evitando repetir accidentalmente el mismo código.

GALPONERO introduce el PIN por POST autenticado. No va en URL, notificaciones,
logs ni auditoría. No entra en el payload persistido de SyncOperation: el endpoint
construye una intención sanitizada y valida/consume el secreto en la misma
transacción que la salida y la entrega.

Los intentos fallidos se guardan aunque no haya despacho. Repetir el mismo UUID
de intento no consume otro intento. Después del límite, solo ADMIN puede
regenerar. Un PIN consumido no sirve para otra entrega; repetir la misma petición
exitosa recupera el recibo sin descontar de nuevo.

## Recorridos manuales desde la PWA

### A. Módulo reproductivo con recojo directo

1. Tener una apertura física real en Etapa 1 y un GALPONERO autorizado. En
   Catálogo de módulos, ADMIN crea «1 macho A + 3 hembras A».
2. ADMIN abre Ventas → Nueva orden. Selecciona un centro, cliente, modalidad
   DIRECTO, módulo, cantidad, moneda, precio y motivo. Comprueba que la
   disponibilidad es referencial. En Etapa 1 el saldo todavía no cambia.
3. GALPONERO abre Ventas → Por confirmar, revisa receta y confirma disponibilidad.
   Verifica reserva IMPAGA y vencimiento; el saldo físico sigue igual.
4. ADMIN abre la orden, carga un comprobante privado válido, revisa referencia e
   importe y valida manualmente el pago. Reserva PAGADA, sin descuento físico.
5. ADMIN genera el PIN y lo entrega al cliente. No copiarlo al motivo ni al aviso.
6. GALPONERO abre Por preparar, usa FIFO o selecciona cada origen real. Guarda
   selección, revisa las cantidades y da conformidad por sus galpones. Si hay
   otros galpones, sus responsables deben contribuir y confirmar.
7. Al llegar el cliente, introduce el PIN, quién realiza la entrega y referencia.
   Confirma salida y entrega juntas. La orden pasa a ENTREGADO.
8. En Etapa 1 comprueba el nuevo saldo y `SALE_DISPATCH` en Kardex. En la orden,
   Trazabilidad del retiro efectivo muestra las pozas, lotes y cantidades.
   Repetir el acuse de la petición no genera otro movimiento.

### B. Carne por peso, conductor y punto de venta

1. ADMIN solicita en un solo centro una línea PESO, por ejemplo dos machos B:
   número de animales = 2; peso realmente acordado = el medido; KG con tres
   decimales, base VIVO/BENEFICIADO explícita y precio por KG. Elegir PUNTO y
   un punto de venta activo. No usar el peso para inferir cuántos animales salen.
2. GALPONERO confirma toda la disponibilidad. ADMIN valida el pago exacto con
   comprobante y asigna un conductor TRANSPORTE vigente para ese centro.
3. GALPONERO selecciona pozas, conserva los lotes y confirma sus orígenes.
   El conductor abre Viajes de cuyes y da conformidad a la preparación actual.
4. GALPONERO confirma la salida física. Solo ahora se descuentan dos animales.
   La orden pasa a EN_RUTA; revisar el movimiento y snapshots de procedencia.
5. Conductor confirma llegada. Si deja el pedido para después, no marcar entrega
   al cliente: queda EN_PUNTO. Si lo entrega directamente, registra al responsable
   físico y la referencia de conformidad: pasa a ENTREGADO.
6. Para retiro posterior, ADMIN registra quién acreditó/realizó la entrega y su
   referencia. La app distingue ese responsable del administrador que registró
   el hecho. El saldo no vuelve a cambiar al llegar ni al retirar.
7. Para probar cambio de peso pospago: antes de salir, ADMIN registra el peso
   corregido. Verificar bloqueo, pago original intacto y diferencia pendiente.
   Resolverla con motivo y evidencia antes de despachar.

### C. Reserva impaga vencida

1. En desarrollo, configurar un plazo corto, por ejemplo
   `CUY_SALES_RESERVATION_MINUTES=1`, y reiniciar Django.
2. Solicitar y confirmar una venta. No pagar. Esperar a que venza según la hora
   del servidor y actualizar: se presenta RESERVA_VENCIDA.
3. Intentar validar pago: se rechaza aunque el comando de limpieza no haya corrido.
4. Ejecutar dos veces:

```powershell
.\.venv\Scripts\python.exe manage.py expire_cuy_sales --username admin-local --batch-size 200
```

5. La reserva queda VENCIDA/liberada, se conserva su historia y solo se crea un
   aviso de vencimiento. El saldo físico nunca cambió. Una reserva PAGADA no se
   libera por este comando, aunque haya pasado su antiguo vencimiento.

### Cancelación y rechazo

GALPONERO puede rechazar una solicitud con motivo. ADMIN puede cancelar antes de
salir. Si hubo pago, debe dejar explícito el tratamiento acordado; sin ello la
cancelación se rechaza. Una orden despachada no admite cancelación ni reingreso
de animales por cambio de estado.

## API y contrato

Todas las rutas están bajo `/api/v1/cuyes/sales`, sin barra final:

- `modules` GET/POST, `availability` GET, `options` GET.
- `orders` GET y `orders/{uuid}` GET.
- `orders/{uuid}/candidates` GET: sugerencia FIFO autorizada, paginada.
- `commands` POST: SALE_CREATE, CONFIRM, REJECT, PROPOSE, PROPOSAL_REVIEW, PAY,
  DRIVER, SELECT, ORIGIN, PICKUP, DEPART, ARRIVE, COLLECT, CANCEL, WEIGH, FINANCE
  y RESOLVE_STOCK, con prefijo SALE_ y payload estricto.
- `orders/{uuid}/pin` POST: generar/regenerar, solo ADMIN.
- `orders/{uuid}/deliver-direct` POST: PIN y salida atómica, solo GALPONERO.
- `vouchers` POST multipart y `vouchers/{uuid}` GET privado, solo ADMIN.

La representación de orden incluye reserva vigente, historia de reservas para
ADMIN, pago/revisiones económicas para ADMIN, preparación/conformidades,
despacho/trazabilidad y entregas. Los operadores reciben una proyección filtrada,
no el objeto administrativo completo. Los errores usan el contrato del proyecto.
`expected_version` obliga a actualizar tras un cambio concurrente.

## Avisos y programación del vencimiento

Solicitud → galponeros del centro. Confirmación/propuesta/rechazo/vencimiento/
faltante → ADMIN. Pago → galponeros; conductor solo si ya tiene una tarea
pagada/asignada. Asignación posterior al pago avisa al conductor. Despacho y
entrega → ADMIN. Los mensajes son genéricos: no contienen cliente, importes,
PIN ni comprobantes. Entran en Notification y la outbox transaccional existentes,
deduplicados por evento/destinatario; Web Push sigue siendo opcional.

El comando procesa como máximo un lote y debe programarse periódicamente.
Ejemplo de cron (documentación; no se instala ni despliega):

```cron
* * * * * cd /ruta/SITRAP && .venv/bin/python manage.py expire_cuy_sales --username admin-operaciones --batch-size 200
```

En Windows, crear una tarea del Programador de tareas cada minuto que ejecute
`.venv\Scripts\python.exe` con argumentos
`manage.py expire_cuy_sales --username admin-local --batch-size 200` y directorio
de inicio del proyecto. Usar una cuenta ADMIN responsable vigente y el entorno
protegido del backend; no pasar claves en argumentos. Revisar códigos de salida.
Dos instancias o dos ejecuciones no duplican vencimientos ni avisos.

El job y el pago bloquean la misma orden/reserva con el mismo bloqueo de centro.
La hora del navegador no determina vencimientos. El aviso no sustituye al estado
actual de la orden ni concede autorización.

## Pruebas

Comandos usuales del README: PostgreSQL real, pytest, Ruff, Django check,
makemigrations --check, OpenAPI validado, tipos generados, npm test y npm run build.

Pruebas de navegador contra Django/PostgreSQL reales, en base temporal:

```powershell
$env:SITRAP_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_cuyes_sales_browser.py -q --basetemp .local/pytest-sales-browser
Remove-Item Env:SITRAP_BROWSER_TESTS
```

Usa Vite en 4182 y datos ficticios aislados, nunca la base de uso local.
El test de Etapa 1 usa 4181; los E2E normales conservan su mock explícito.
No se activa tracing del navegador para las pruebas de PIN.
Android físico, infraestructura de backups, escaneo antivirus y Web Push real
siguen necesitando verificación/configuración en el entorno de operación.
