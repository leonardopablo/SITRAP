# SITRAP — descripción general y requerimientos

**Revisión 3 · 2 de octubre de 2026. Especificación vigente del MVP de leche.**

Documentos coordinados: [Datos y UML](SITRAP_02_arquitectura_base_datos.md), [Frontend](SITRAP_03_frontend_tareas.md), [Backend](SITRAP_04_backend_tareas.md). Esta revisión sustituye las anteriores. El catálogo de comandos/API y la matriz de permisos tienen como fuente principal el documento 04; el modelo y sus estados, el documento 02. Los IDs de tareas pertenecen a esta revisión.

## 1. Proyecto y problema

SITRAP es un sistema de información para mejorar la trazabilidad de productos de los centros de producción de Cotosh/Kotosh y Canchán, administrados por DIPROPSA. Se validará la denominación institucional antes del piloto. Los registros actuales se distribuyen entre cuadernos y hojas de cálculo. La primera implementación seguirá la leche desde la producción por vaca hasta su recepción en el punto de venta.

Vilma registra litros por vaca y prepara bolsas nominales de un litro. Lolo recoge la cantidad declarada, sin volver a pesar cada bolsa, y María confirma la recepción. El sistema reduce escritura repetida: una persona registra la entrega y las siguientes dan conformidad. Cada acción conserva su autor y fecha. La conformidad autenticada es evidencia interna, no una firma digital certificada.

## 2. Alcance confirmado

Incluye cuentas individuales, cuatro perfiles, centros/productos configurables, vacas, ordeños, lote de origen, entrega, conformidades, correcciones por aprobación, notificaciones internas y push, calendarios, métricas y PDF. PWA para Android y escritorio con captura local y sincronización.

Se aplazan inventario físico/comercial, pérdidas físicas, ventas, boletas, Tesorería, conciliación financiera, sobrantes/transformaciones, mezclas, IA y módulo de cuyes. No se implementa recepción con diferencia ni resolución administrativa que sustituya aceptaciones. Si una persona no está conforme, puede dejar la operación pendiente; el sistema nunca confirma automáticamente ni convierte una pérdida en un error de escritura. El piloto no resuelve todos los casos excepcionales del proyecto completo.

Las fotos de cuyes orientan la ampliación futura (centros, galpones, pozas/jaulas y conteos mensuales), pero no amplían el MVP. Se reutilizarán usuarios, productos, ubicaciones, auditoría, informes y notificaciones; se añadirán sus tablas/reglas cuando se levanten los requisitos. Incorporar un producto al catálogo no habilita automáticamente su proceso operativo.

## 3. Perfiles y personas

| Perfil | Acciones y vista |
|---|---|
| PRODUCCION | Vilma u otra persona asignada: producción por vaca, preparación de entrega, solicitud de corrección, gráficos y PDF de su centro. |
| TRANSPORTE | Lolo u otra persona asignada: recogidas, calendario diario/mensual, cantidades recogidas y recepciones de sus entregas, PDF. |
| RECEPCION | María u otra persona asignada: recepciones pendientes, conformidad, historial por período y PDF. |
| ADMIN | Cuentas, ámbitos, catálogos, consulta general e informes; no aprueba en nombre de operadores. |

Los perfiles no están ligados a nombres escritos en el código. Quien cubra a otra persona utiliza su cuenta y recibe la asignación correspondiente. No compartir credenciales. Los reemplazos cubren operaciones nuevas o pendientes sin aceptación previa según la reasignación definida en el documento 02; no heredan firmas históricas.

En este MVP la consulta global es del administrador. No se promete acceso de oficina independiente sin crear sus cuentas/permisos. Un perfil de supervisión de solo lectura podrá incorporarse después. “Permisos” significa acceso a funciones y datos; el trabajo cotidiano no requiere aprobación administrativa adicional.

## 4. Flujo cotidiano

1. Vilma registra litros por vaca, fecha y turno. Puede guardar borrador. Al confirmar, el sistema calcula el total y crea un lote único. Todavía no avisa a Lolo.
2. Desde esa producción prepara la entrega. Producto, bolsa de 1 L, centro, conductor y destino vienen preseleccionados cuando existe una sola opción válida. Revisa bolsas/litros y pulsa “Enviar a transporte”.
3. El servidor guarda la solicitud y crea el aviso para el conductor. Lolo ve cantidad, origen y destino; pulsa “Estoy conforme”. No vuelve a escribir la cantidad.
4. Se guarda la recogida, la entrega pasa a EN_CAMINO y María ve en la app “Pendiente de recibir: 20 litros”; el aviso del teléfono usa texto genérico hasta abrirla.
5. Cuando la leche llega físicamente, María pulsa “Confirmar recepción”. Se guarda ese hecho y se actualiza el historial/calendario. Vilma y Lolo reciben aviso de recepción.

Los datos se guardan en cada paso. Leer un aviso o aprobar una corrección no confirma una recogida ni una recepción física. La cantidad producida puede ser mayor que la entregada: 23,5 L producidos y 20 L entregados dejan 3,5 L “no vinculados a entregas registradas”, sin afirmar que sean stock, pérdida o venta.

## 5. Ediciones y correcciones acordadas

### Antes de la recogida

Un borrador se puede editar. Una solicitud ya enviada, pero todavía no recogida, puede ser revisada por producción: se publica una nueva versión y se actualiza el aviso del conductor. Lolo solo puede aceptar la versión vigente. Si edición y recogida llegan simultáneamente, el servidor acepta una y obliga a revisar la otra.

### Después de que transporte dio conformidad

Producción solicita corregir una cantidad, especificando entrega, valor anterior, valor propuesto y motivo. Se guarda una propuesta inmutable y se avisa a transporte y recepción.

**Se requieren ambas aprobaciones.** El registro vigente sigue siendo el anterior hasta obtenerlas. La segunda aprobación válida aplica el cambio automáticamente en una transacción, conserva el historial y notifica el resultado. Si se quiere proponer otro valor, se retira la solicitud y se crea otra sin reutilizar aprobaciones.

Los aprobadores son quien confirmó la recogida y quien confirmó la recepción; si esta todavía no ocurrió, se utiliza el receptor asignado. Aprobar antes de recibir significa aprobar la corrección documental: posteriormente deberá confirmar la recepción física. La entrega mantiene su etapa logística al aplicar la corrección.

Un rechazo termina esa propuesta y conserva el dato vigente. La falta de respuesta la mantiene pendiente. ADMIN no puede forzar su aplicación. Los cambios históricos requieren a sus participantes originales; si no están disponibles, quedan pendientes en esta etapa del proyecto.

### Producción y entrega son registros distintos

Corregir litros por vaca se realiza en producción y conserva versiones. No cambia automáticamente la cantidad que Lolo y María aceptaron. El nuevo total debe cubrir las cantidades vinculadas a entregas activas y las reservas máximas de propuestas pendientes definidas en 02 §10; si no alcanza, primero se corrige la entrega mediante el flujo anterior. Corregir una entrega tampoco cambia la producción por vaca.

Una producción anulada conserva historial, pero deja libre su combinación centro/fecha/turno para registrar el reemplazo. Se prohíbe anular cuando hay entregas publicadas no canceladas asociadas. Fecha/turno equivocados en una producción ya vinculada se dejan para revisión; no se reasignan hechos históricos silenciosamente.

## 6. Notificaciones incluidas

| Evento | Destinatarios |
|---|---|
| Solicitud enviada o revisada antes de recogida | Conductor asignado. |
| Recogida confirmada | Receptor asignado. |
| Recepción confirmada | Emisor de la entrega y conductor. |
| Corrección solicitada | Los dos aprobadores definidos. |
| Corrección aplicada o rechazada | Solicitante y ambos aprobadores. |
| Corrección retirada | Ambos aprobadores. |

Cada aviso se conserva en la bandeja interna y puede generar push en el teléfono si el usuario lo habilita. Tocar abre el registro; no autoriza cambios. La solicitud del permiso del navegador se hace al pulsar “Activar notificaciones”. Rechazar ese permiso no impide usar SITRAP.

El aviso se crea después de validar la operación en servidor, dentro de la misma transacción que genera una tarea persistente de envío. El push puede demorarse, repetirse o no mostrarse por red/configuración del dispositivo; la bandeja y el estado de la operación son la referencia. Si la captura es offline, el aviso remoto se genera después de sincronizarla. Las notificaciones no sustituyen la sincronización de datos.

## 7. Requerimientos funcionales

| ID | Requerimiento |
|---|---|
| RF01 | Login/logout, cambio de contraseña y restablecimiento por ADMIN; sin registro público. |
| RF02 | Cuatro perfiles con ámbitos y asignaciones comprobados por servidor. |
| RF03 | Catálogos generales de centros, productos/presentaciones, especies, turnos y vacas; desactivación con historial. |
| RF04 | Borrador y confirmación de ordeño por vaca; unicidad entre registros no anulados por centro/fecha/turno. |
| RF05 | Un lote por producción confirmada y consulta de su procedencia. |
| RF06 | Preparar, enviar, revisar antes de recogida y cancelar una entrega aún no recogida. |
| RF07 | Conformidad de recogida sin recapturar cantidad. |
| RF08 | Conformidad de recepción física y actualización de la misma entrega. |
| RF09 | Solicitud de corrección de cantidad posterior a recogida con motivo y dos aprobaciones. |
| RF10 | Versiones y auditoría de rectificación de producción, correcciones y decisiones. |
| RF11 | Calendario de transporte e historiales por día/mes/período. |
| RF12 | Producción por vaca, total, número de ordeños y días registrados. |
| RF13 | PDF filtrado de producción, viajes, recepciones y resumen administrativo. |
| RF14 | Captura local, cola durable, idempotencia, dependencias y recuperación de sesión. |
| RF15 | Estados local/enviado/aceptado, pendientes y última actualización visibles. |
| RF16 | Cuentas, ámbitos, asignación de reemplazos y desactivación conservando autoría. |
| RF17 | Bandeja interna, contador de no leídos y acceso al registro asociado. |
| RF18 | Activación/desactivación de push por dispositivo; avisos operativos y de correcciones. |

## 8. Requerimientos no funcionales

Android primero, adaptable desde 320 px; administración en escritorio. Objetivo WCAG 2.2 AA, texto claro, cantidades con unidad, áreas táctiles grandes y movimiento reducido. Ilustraciones de vacas/bolsas y animaciones breves; éxito local y éxito del servidor se presentan de manera distinta.

HTTPS, sesiones Django, CSRF, contraseñas administradas por Django, copias de seguridad y prueba de restauración. Reintentos no duplican hechos ni avisos internos. Servidor con fecha UTC e informes en America/Lima. Sesión propuesta de 12 h y preparación offline de 7 días, configurables y a validar en campo.

Meta de piloto: solicitud visible en la app abierta dentro de 15 s con red estable, mediante actualización periódica y manual. No se garantiza plazo de entrega de push. Las copias locales sobreviven a reinicios mientras se conserve almacenamiento del navegador; no se garantiza recuperación después de borrar datos o perder el teléfono.

## 9. Offline y cuentas

Primer ingreso y preparación requieren internet. Después se pueden guardar ordeños, preparar solicitudes y confirmar documentos previamente descargados. Si el origen solo existe en el teléfono de Vilma, Lolo guarda una nota provisional y posteriormente la vincula explícitamente a la solicitud correcta. No se crean lotes ficticios ni se vincula por coincidencia de cantidades.

Sesión vencida: conservar pendientes, reautenticar la misma cuenta, renovar CSRF y reintentar. Cambio de cuenta: aislar copias y pendientes; nunca transmitirlos como el nuevo usuario. Tras 7 días sin preparación, conservar pendientes y permitir solo notas provisionales hasta renovar acceso. Creación de propuestas de corrección y administración requieren conexión; aprobaciones offline solo para propuestas descargadas y nuevamente validadas por servidor.

## 10. Indicadores de evaluación del piloto

| Indicador | Definición / medición |
|---|---|
| Tiempo de registro | Mediana de minutos de una entrega desde preparación hasta envío; comparar tareas equivalentes en papel y app. |
| Tiempo de reconstrucción | Minutos para ubicar producción, recogida y recepción de una entrega seleccionada. |
| Recepciones documentadas | Entregas con recepción confirmada / entregas recogidas del período ×100; indicar corte y pendientes aún en camino. |
| Integridad | Registros completos según campos obligatorios / registros evaluados ×100. |
| Correcciones | Entregas con corrección solicitada y tiempo de resolución; separar rechazadas/pendientes. |
| Demora de sincronización | Tiempo entre hecho declarado y aceptación central, con advertencia si el reloj del dispositivo es inconsistente. |
| Facilidad de uso | Tareas completadas, errores y ayuda requerida por Vilma/transporte/recepción durante pruebas. |

Los registros históricos solo sirven como línea de base si tienen datos comparables. Producción por vaca es una métrica operativa; no demuestra rentabilidad ni justifica decisiones veterinarias por sí sola.

## 11. Desarrollo y ampliación

Django/DRF modular, PostgreSQL y React/TypeScript PWA. Puede desplegarse en Azure manteniendo UI/API bajo un mismo origen HTTPS, base administrada y proceso de envío push según documento 04. El módulo lechero no debe imponer litros/ordeños a otros productos. Catálogos y servicios comunes se reutilizan; procesos nuevos añaden módulos mediante migraciones.

Cada tarea de frontend/backend termina con verificación pertinente, commit propio y push a GitHub. Los documentos definen trabajo pendiente; no afirman que ya exista implementación. Cuatro archivos de revisión 3 forman el paquete vigente; copias anteriores deben quedar fuera de la carpeta de implementación.

Pendiente de campo: nombres oficiales, turnos, códigos de vacas, responsables ADMIN y receptores suplentes, conexión y notificaciones en Android reales. Estas validaciones no autorizan a incorporar automáticamente cuyes, ventas o una vía excepcional de aprobación.
