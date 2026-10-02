# SITRAP — frontend, experiencia visual y tareas

**Revisión 3 · 2 de octubre de 2026.**  
[General](SITRAP_01_descripcion_general.md) · [Datos/UML](SITRAP_02_arquitectura_base_datos.md) · [Backend/API](SITRAP_04_backend_tareas.md).

## 1. Decisión de producto y tecnologías

Una PWA para Android, adaptable a escritorio, con un login y navegación según los roles PRODUCCION, TRANSPORTE, RECEPCION y ADMIN. Vilma registra la entrega; Lolo y María confirman la cantidad que ya ven. Campos y botones usan nombres de tareas, no términos de base de datos.

React + TypeScript + Vite; React Router; Tailwind CSS conectado a variables CSS; TanStack Query para datos remotos; Dexie/IndexedDB para caché autorizado y cola offline; vite-plugin-pwa con Service Worker personalizado para instalación, recursos y Web Push; React Hook Form/Zod para formularios; Recharts para gráficos; Vitest/Testing Library y Playwright para comprobaciones pertinentes. Fijar versiones compatibles y lockfile al iniciar.

Un único Service Worker integra caché y handlers push/notificationclick, evitando registros que se sobrescriban. La notificación del teléfono complementa la bandeja interna. Actualización de solicitudes desde la primera pantalla operativa: polling cada 10 s mientras está visible y online, refresco manual y al recuperar foco/conexión. No esperar a una tarea tardía para que Lolo vea solicitudes nuevas. Push no es la fuente de verdad y no reemplaza consultar el estado del servidor.

No se implementan ahora ventas, caja, inventario físico, diferencias de cantidad, recepción parcial ni gestión de pérdidas. No hay botón “Reportar diferencia” o “Recibir con diferencia” en este alcance. Si alguien no está conforme, deja la entrega pendiente y coordina; nunca se confirma automáticamente.


## 2. Cómo se adapta la guía recibida

| Propuesta recibida | Decisión para SITRAP |
|---|---|
| Verde, amarillo y formas suaves | Se conservan como base visual, con ilustraciones visibles en tareas de campo. |
| Inspiración Apple | Se conserva claridad y jerarquía; interfaz web familiar para Android. No se implementa Liquid Glass ni se imitan controles iOS. |
| Ilustraciones solo en bienvenida/vacíos | Se amplían a éxitos breves: vaca registrada, recogida y recepción. |
| Animaciones de 150–200 ms | Controles mantienen 150–200 ms; ilustración de confirmación hasta 600 ms, una vez y sin bloquear. |
| Tablas/lotes como inicio general | En campo, inicio por tareas. Tablas para administración e historial extenso. |
| Formulario origen → producto → movimiento | En piloto los datos conocidos se rellenan; Vilma revisa bolsas y envía. No obligar a cuatro pasos. |
| QR público, mezclas, productores y predios | Fuera del MVP; no añadir pantallas por aparecer en una guía genérica. |
| Estado “Verificado” | Usar “Recogida confirmada” o “Recepción confirmada”, evitando sugerir certificación. |
| Logo conceptual/PNG mencionado | Solo dirección de marca: no se recibió un logo vectorial en estos adjuntos. Diseñarlo como tarea; no afirmar que está listo. |
| Tipografía del sistema | Se conserva para rendimiento y uso offline; Nunito Sans opcional solo si se sirve localmente y se valida. |

Identidad: **“Cada producto tiene una historia”** puede usarse en acceso/bienvenida. En las tareas importa el verbo concreto: “Enviar a Lolo”, “Confirmar recogida”, “Confirmar recepción”. La marca general usa ruta/hoja, no exclusivamente una vaca; la vaca identifica el proceso lechero.

## 3. Sistema visual y accesibilidad

- Paleta base: verde `#237A57`, verde oscuro `#173D32`, amarillo `#F4C95D`, verde suave `#EAF5EE`; superficies claras y texto `#1D1D1F`.
- Color por tarea como apoyo: verde producción, azul transporte, amarillo suave recepción. Siempre título, icono y estado escrito; el color no codifica por sí solo.
- Tarjetas redondeadas de 16 px, márgenes móviles de 16 px, texto normal 16 px y ayudas 14 px. Cantidad principal 32–40 px con unidad visible.
- Botones operativos de al menos 48 px de alto, área táctil secundaria mínima del proyecto 44×44 px. Una acción principal por tarjeta.
- Amarillo con texto oscuro; nunca texto blanco sobre amarillo. No usar borde decorativo tenue como único límite de campo.
- Contraste objetivo WCAG 2.2 AA: texto normal 4,5:1; grande y controles esenciales 3:1 cuando corresponda. Verificar combinaciones reales, incluidos foco, deshabilitado, error y tarjeta coloreada.
- Funciona con zoom 200 %, reflujo a 320 px, teclado y lector de pantalla. Formularios conservan etiquetas y errores asociados. Foco visible; diálogos devuelven foco al cerrar.
- Fuentes del sistema, números tabulares, español peruano, unidades siempre visibles. No afirmar que kg equivale a L.
- Móvil: máximo cuatro destinos en barra inferior. Escritorio: lateral de unos 240 px. Formularios hasta 720 px; contenido máximo 1280 px.
- Sin modo oscuro en el piloto: requiere paleta comprobada, no inversión automática de colores.

## 4. Ilustraciones y movimiento especificados

| Situación | Recurso propuesto | Comportamiento y texto |
|---|---|---|
| Acceso/bienvenida | Paisaje sencillo con campo, ruta y productos | Estático, no distrae del login. |
| Animal registrado | Vaquita sonriente | Gesto breve de 400–600 ms; “Vaca registrada”. Solo tras acuse del servidor. |
| Producción confirmada | Vaca y gota/balde | Aparición breve; total y “Producción confirmada”. |
| Solicitud enviada | Bolsa de leche junto a ruta | Movimiento corto; “Solicitud enviada a Lolo”. No indica que ya la leyó. |
| Recogida confirmada | Bolsa y check, pequeño vehículo | Check breve; “Recogida confirmada”. |
| Recepción confirmada | Balde/bolsas y check | “Recepción confirmada”; el viaje queda completado en el sistema. |
| Guardado offline | Teléfono e icono de reloj | “Guardado en este teléfono. Pendiente de enviar”. Sin animación que sugiera éxito remoto. |
| Error de registro | Icono claro y explicación | Sin mascota celebrando, sacudidas o dramatización. |
| Sin tareas | Ilustración de campo tranquila | “No tienes recogidas pendientes”. No confundir con error de carga. |

Reglas: sin bucles, confeti, audio ni esperas obligatorias. No desplazar formularios al animar. SVG decorativo con `aria-hidden`; resultado en texto y anuncio accesible. Respetar `prefers-reduced-motion` y ajuste propio “Reducir animaciones”; en cualquiera de los dos casos mostrar versión estática. Mantener estado final visible en tarjeta/historial, no solo toast.

Presupuesto de proyecto: preferir SVG, máximo inicial de 100 KB por ilustración optimizada y de 300 KB para el conjunto del piloto; medir en los Android reales. Recursos empaquetados, sin necesidad de internet para cargarlos. No se han generado aún estos dibujos ni el prototipo Figma: aquí se especifica su implementación.


## 5. Pantallas por rol

### Acceso, cuenta y conexión

Logo, saludo, usuario/contraseña, mostrar contraseña, “Ingresar” y ayuda de contacto interno. `autocomplete=username` y `current-password`; el navegador puede ofrecer guardar la contraseña, la app no la almacena. Cambio obligatorio tras contraseña temporal. Roles y ámbito salen de `/auth/me`, no de una selección libre de privilegios.

Con varios roles autorizados, selector de espacio de trabajo. Nombre de cuenta, centro y rol visibles para evitar registrar como otra persona. Personal de reemplazo usa su propia cuenta/asignación. Un teléfono no transfiere automáticamente pendientes al siguiente usuario.

Indicador persistente: “Con conexión”, “Sin conexión” y cantidad de operaciones pendientes. “Guardado en este teléfono” se distingue de “Guardado en el sistema”. Sesión vencida conserva datos y solicita ingresar con la misma cuenta. Pantalla de sincronización accesible desde el indicador; no llenar el inicio de mensajes técnicos.

Campana común abre Avisos; acceso a “Notificaciones del teléfono” en preferencias. Sin permiso push, la app conserva todas las funciones.

### Vilma / PRODUCCION

Navegación móvil: **Hoy · Producción · Vacas · Historial**; avisos y cuenta en cabecera.

| Pantalla | Contenido y acciones |
|---|---|
| Hoy | Fecha/centro, registrar producción, borradores, entregas pendientes, avisos de corrección. |
| Registrar producción | Fecha/turno preseleccionados, lista de vacas código/nombre y litros; total calculado. Cero explícito distinto de vacío. Guardar borrador y Revisar. |
| Confirmar producción | Resumen por vaca/total y Confirmar producción. Tras acuse aparece Preparar entrega. |
| Preparar entrega | Lote/origen derivados, bolsas enteras de 1 L y equivalente, conductor/destino/receptor asignables desde `/assignment-options`; valores habituales preseleccionados. Un formulario corto y Enviar solicitud. |
| Entrega enviada | Cantidad, destinatarios, estado y línea de tiempo. Antes de recogida: Modificar solicitud o Cancelar, con motivo. Después: Solicitar corrección. |
| Solicitar corrección | Cantidad vigente, cantidad propuesta, motivo, nombres de ambos aprobadores. Explicar “Se actualizará cuando ambos aprueben”. |
| Vacas | Alta corta y detalle con producción por período. Campos disponibles del modelo; no pedir estado de lactancia sin modelo. |
| Análisis de producción | Litros por vaca, tendencia, promedio y días registrados; filtros equivalentes. Sin afirmar rentabilidad ni recomendar descarte animal. |
| Historial | Producción y entregas por fecha, detalles/correcciones y PDF filtrado. |

Alta de vacas, rectificar producción y anular requieren conexión. Rectificar litros por vaca no corrige automáticamente una entrega aceptada: explicar esa separación en pantalla. Anulación solo cuando backend la permite; versión anterior siempre consultable. Si fecha/turno no puede cambiarse por vínculos existentes, mostrar motivo, no una opción de “forzar”.

### Lolo / TRANSPORTE

Navegación: **Hoy · Diario · Pendientes**.

- Inicio: solicitudes por recoger y entregas en camino, actualizado desde su primera implementación.
- Tarjeta: “Vilma te entrega”, centro, fecha/código, **20 bolsas · 20 L**, destino. Acción **Confirmar recogida**. Un toque cuando los datos ya se ven, sin exigir reescribir cantidad ni modal redundante.
- Mientras envía: “Confirmando…” y botón bloqueado de ancho estable. Acuse: “Recogida confirmada”; cambia a En camino y genera aviso a María. Offline: “Confirmación guardada en este teléfono. Pendiente de enviar”.
- No existe un segundo formulario obligatorio de Lolo al llegar; recepción de María completa el recorrido.
- **Diario visual:** calendario mensual con litros recogidos y litros recibidos en destino como medidas separadas. Pulsar día abre entregas. Listado equivalente accesible, filtros y Descargar PDF por período.
- **Pendientes:** recogidas y solicitudes de corrección por decidir, separadas por título. No confundir avisos no leídos con trabajo sin completar.
- Sin solicitud descargada: nota provisional local para vincular manualmente después. Se marca como nota, sin firma, envío o cantidad oficial. No generar un traslado ficticio.

### María / RECEPCION

Navegación: **Hoy · Recepciones · Pendientes**.

- Hoy: entregas en camino, cantidad esperada y recibido hoy; no ventas, caja ni cobro.
- Tarjeta: Lolo, origen, bolsas/litros, código y estado. **Confirmar recepción** solo al recibir físicamente. Ver notificación o aprobar corrección no realiza esta acción.
- Recepciones: listado por fecha, detalle/historial, cantidad vigente con marca de corregida si corresponde, PDF del período.
- Corrección pendiente: mostrar “Hay una corrección por aprobar antes de confirmar la recepción”. Abrir propuesta permite aceptar/rechazar, aunque la leche aún no haya llegado. Si solo ella aprobó, mostrar a quién falta responder; mantener recepción bloqueada hasta cierre de la propuesta.
- Cuando ambos aprueban, actualizar cantidad y habilitar recepción si sigue EN_CAMINO. Si ya estaba RECIBIDO, mostrar corrección sin solicitar una segunda recepción.

### ADMIN

Resumen de producción, recogido y recibido; filtros por centro/producto/período, pendientes y correcciones. Secciones: Producción, Entregas, Correcciones, Catálogos, Usuarios y Reportes. Puede consultar globalmente, descargar resumen y configurar cuentas/ámbitos; no aprobar como Lolo o María.

Usuarios: alta, contraseña temporal, asignación de rol/ubicación, desactivar y reset. Catálogos: centros, productos habilitados por centro, presentaciones, turnos y animales. No pedir cantidad de existencias al crear producto.

Reemplazos: asignación de otra cuenta para trabajo nuevo; antes de recogida, producción revisa destinatarios. ADMIN puede reasignar receptor de una entrega EN_CAMINO únicamente si no se recibió ni existe ninguna solicitud de corrección histórica. Mostrar motivo, responsable anterior/nuevo y registro auditable. No cambiar quién ya confirmó recogida/recepción ni delegar aprobaciones históricas.

No hay rol de oficina adicional en este MVP. El acceso de cada persona depende de su cuenta y roles acordados; no afirmar que Abraham/Paul tienen un panel sin privilegios administrativos que todavía no se ha definido. Si se necesita lectura global sin administración, se añadirá explícitamente después.

## 6. Correcciones: experiencia y decisiones

Detalle con fecha/código, cantidad vigente → propuesta, motivo y dos filas: Transporte y Recepción, cada una Pendiente/Aceptó/Rechazó con responsable y hora. Los nombres vienen de la solicitud, no de texto fijo Vilma/Lolo/María.

**Antes de recogida:** modificar solicitud publica revisión nueva. Lolo al abrir un aviso viejo recupera la versión vigente. Si pulsó sobre una obsoleta, explicar “La solicitud cambió; revisa la cantidad actual” y exigir una nueva decisión.

**Después de recogida:** Vilma propone corrección. Botones para cada aprobador: “Aceptar corrección” y “Rechazar”; rechazo pide motivo. Propuesta no editable una vez enviada. Solo segunda aceptación válida produce “Corrección aplicada”. Primera: “Aprobaste la corrección; falta la otra aprobación”.

No usar “Autorizar edición” para permitir después cualquier valor: aprueban exactamente el cambio mostrado. Si Vilma desea otra cifra, retira y crea nueva solicitud. Solicitante puede retirar mientras pendiente; se conserva historial de decisiones previas. Rechazo/retiro mantiene cantidad vigente anterior. Sin respuesta no se aplica automáticamente y ADMIN no tiene botón para saltar aprobaciones.

Aprobación offline requiere propuesta descargada, conserva version_id y expected_version. Conflicto exige consultar estado: mostrar “Cambió el estado de esta solicitud; revísala antes de reenviar”. No regenerar silenciosamente una aprobación. Nunca mostrar éxito definitivo solo porque se presionó el botón.

La línea de tiempo diferencia producción, publicación, recogida física, propuesta/decisiones y recepción física. Fecha de corrección no sustituye fecha de entrega. Tras corregir, el resumen muestra valor vigente y acceso al original, sin fingir una firma nueva.

## 7. Avisos en la app y notificaciones del teléfono

### Bandeja persistente

Campana con contador no leído; lista por fecha con Todos/No leídos, texto claro y acción “Ver entrega” o “Ver corrección”. Marcar leído mediante API, independiente de confirmar el trabajo. Mostrar vacíos, carga, error recuperable y última actualización. Polling cada 10 segundos solo visible/online, actualización al recuperar foco o recibir mensaje del Service Worker.

Tipos/destinatarios exactos en **04 §6**, sin copiar un catálogo diferente aquí. Backend es quien crea avisos tras aceptar el evento. Si una solicitud se modifica/cancela, el aviso anterior abre el estado actual; no mantiene botones para actuar sobre una versión vieja.

### Activación push

Tras el primer acceso, tarjeta no bloqueante: “Recibe avisos de entregas y correcciones en tu teléfono”, con **Activar notificaciones** y **Ahora no**. Pedir permiso del navegador únicamente al pulsar Activar. Comprobar soporte de Service Worker, PushManager y Notifications antes; no mostrar una promesa si falta soporte.

| Situación | Mensaje y acción |
|---|---|
| Compatible, aún no solicitado | Explicación y Activar. |
| Permiso concedido y suscripción guardada | “Avisos del teléfono activados”; opción Desactivar. |
| Permiso rechazado | Explicar cómo revisar permiso del sitio; no insistir con diálogos repetidos. |
| Sin soporte o sin suscripción válida | “Consulta tus avisos dentro de SITRAP”; permitir reintentar cuando proceda. |
| Sin conexión al activar | “Conéctate para activar los avisos”; mantener bandeja local disponible. |
| Fallo al guardar suscripción | No declarar activación completa; reintento seguro e idempotente. |

Usar clave VAPID pública del backend, suscribir navegador y registrar suscripción de la cuenta/dispositivo propios. Revalidar suscripción al iniciar sesión; no reutilizar silenciosamente la de otra cuenta. Desactivar desde ajustes retira suscripción de backend/navegador; logout sigue el contrato de 04 §2.

Service Worker muestra push con texto genérico y tag estable por notificación. Sin litros/nombres en pantalla bloqueada por defecto. `notificationclick` abre/enfoca ruta interna permitida; si requiere login, recuperar destino tras autenticación y consultar API. No ejecutar recogida, recepción o aprobación en el Service Worker ni directamente desde push.

El aviso del teléfono depende de permiso, red y navegador. La app no promete entrega inmediata, vibración o lectura. En ausencia de push, bandeja y tareas siguen disponibles. Push recibido puede avisar a las ventanas para actualizar; no inserta hechos de negocio confiando en el payload.

## 8. Offline, conflictos, sesión y PDF

Datos locales separados por cuenta y dispositivo. Precargar mediante bootstrap todos los datos autorizados necesarios, incluidos lotes y entregas abiertas antiguas, correcciones, opciones asignables y avisos, según 02 §12 y 04 §5. TanStack Query maneja lecturas; IndexedDB conserva operaciones. No escribir el mismo comando por dos rutas independientes.

Un servicio de comandos guarda primero intención/UUID/dependencias; si hay conexión, la envía; si no, muestra pendiente. Cuando llega acuse central, aplica resultado y actualiza caché. Reanudación usa el mismo UUID, incluso si la app se cerró durante ENVIANDO. Publicar padre e hijos respeta dependencias; versiones en conflicto detienen la cadena.

Pantalla Pendientes de sincronización: acción, fecha, estado legible, error y Reintentar/Ver detalle. Rechazados conservan información; no ofrecer “forzar”. Notas provisionales separadas de operaciones confirmadas. Mostrar hora última sincronización.

Vilma y Lolo en el mismo lugar pueden confirmar desde sus teléfonos solo cuando la solicitud ya está en el servidor y descargada por Lolo. Un registro aún local no produce notificación remota. Si falla internet, nota provisional y posterior vinculación explícita; no implementar intercambio entre dispositivos no definido.

Sesión expirada conserva formularios/outbox y pide la misma cuenta. Logout con pendientes ofrece sincronizar o bloquear conservándolos, explicando su alcance offline. Al cambiar de cuenta, datos previos quedan bloqueados; no mezclarlos en la pantalla nueva. Solicitar almacenamiento persistente si está disponible, sin prometer inmunidad al borrado del navegador.

**PDF:** selector período/filtros y Descargar. Si el teléfono tiene pendientes, advertencia frontend “Este informe incluye solo lo sincronizado; tienes N operaciones pendientes”, con Sincronizar primero o Descargar de todos modos. Backend no conoce esos pendientes. PDF mensual/semanal usa corte declarado del servidor, no una exportación de datos locales presentada como definitiva. Descargar requiere conexión en el MVP.

## 9. Desarrollo en tareas cortas

**Regla para todas las tareas:** cada funcionalidad terminada se prueba, se documenta y se comitea en el repositorio GitHub del proyecto. Un commit por funcionalidad con el mensaje sugerido o equivalente; publicar en la rama de trabajo configurada según el flujo del repositorio. No un único commit al terminar todas las pantallas. Pruebas junto a cada tarea; integración final complementa, no reemplaza esa verificación.

Dependencias Bxx remiten a tareas de backend 04 §8. Un mock generado desde contrato permite diseñar antes, pero no da por cerrada una función integrada. Los Bxx citados son mínimos; las guardas y correcciones completas se verifican antes del piloto.

| ID | Entrega acotada | Depende de | Verificación y commit sugerido |
|---|---|---|---|
| F01 | React/TS/Vite, router, lockfile y runner | B01 contrato base | Build y navegación; `chore: iniciar frontend`. |
| F02 | Tokens visuales y componentes base | F01 | Foco, contraste, botones/campos; `feat: crear base visual`. |
| F03 | Logo ruta/hoja en SVG y variantes pequeñas | F02 | Legible, genérico para futuros productos; `design: crear logo sitrap`. |
| F04 | Ilustraciones SVG de vaca, bolsa, ruta y vacío | F02 | Tamaño, estado estático, sin recursos remotos; `design: crear ilustraciones`. |
| F05 | Login, cambio de contraseña y sesión | F02, B04 | CSRF, error y sesión vencida; `feat: iniciar sesion`. |
| F06 | Shell por roles, centro/cuenta y bloqueo | F05, B05 | No mezclar cuentas/ámbitos; `feat: navegar por rol`. |
| F07 | Cliente API y tipos desde OpenAPI | F05, B06 | Errores normalizados y UUID estable; `feat: conectar contrato api`. |
| F08 | Service Worker único, instalación y recursos | F01 | App preparada abre offline; `feat: instalar pwa`. |
| F09 | IndexedDB, comandos/outbox por cuenta | F07, F08, B06 | Reinicio conserva UUID y pendientes; `feat: guardar operaciones locales`. |
| F10 | Motor de sincronización y dependencias | F09, B29 | Padre ausente, replay, conflicto; `feat: sincronizar registros`. |
| F11 | Preparación/cambios, sesión y panel de pendientes | F06, F10, B28, B30 | Abiertas antiguas, revocación y misma cuenta; `feat: mostrar estado de conexion`. |
| F12 | Bandeja interna y refresco compartido | F07, B18 | No leído distinto de pendiente; polling visible desde aquí; `feat: consultar avisos`. |
| F13 | Lista/alta/edición de vacas | F06, F07, B12 | Campos, errores, autorización; `feat: gestionar vacas`. |
| F14 | Borrador de ordeño por vaca | F09, F11, F13, B13 | Vacío/cero, suma, recuperar borrador; `feat: registrar ordeno`. |
| F15 | Revisión y confirmación de producción | F14, B14 | Una confirmación, lote y estado local; `feat: confirmar produccion`. |
| F16 | Preparar entrega y opciones asignables | F15, B11, B17 | Defaults válidos, bolsas enteras; `feat: preparar entrega`. |
| F17 | Enviar solicitud y consultar detalle | F12, F16, B19 | Aviso solo tras acuse; `feat: enviar solicitud de leche`. |
| F18 | Revisar/cancelar solicitud antes de recogida | F17, B20 | Conflicto y versión anterior; `feat: modificar solicitud`. |
| F19 | Inicio Lolo y Confirmar recogida | F11, F12, F17, B21 | Refresco, un toque, offline y doble clic; `feat: confirmar recogida`. |
| F20 | Inicio María y Confirmar recepción | F11, F12, F19, B22 | Solo recepción física, bloqueos actuales; `feat: confirmar recepcion`. |
| F21 | Proponer corrección con antes/después | F18, F20, B23 | Motivo y propuesta fija, bloquear recepción pendiente; `feat: solicitar correccion`. |
| F22 | Decidir corrección y mostrar dos aprobadores | F21, B24, B25 | Orden indiferente, rechazo, sin éxito prematuro; `feat: decidir correccion`. |
| F23 | Retirar y consultar historial de corrección | F22, B25 | Sin reusar decisiones; `feat: consultar revisiones`. |
| F24 | Preferencias push y registro de suscripción | F08, F12, B31 | Permiso por gesto, denegación, cuenta correcta; `feat: activar avisos del telefono`. |
| F25 | Recepción push, click y apertura autorizada | F24, B33 | Cerrada/abierta, aviso viejo, sesión vencida; `feat: abrir notificaciones push`. |
| F26 | Calendario diario/mensual de Lolo | F19, F23, B35 | Recogido/recibido separados; `feat: consultar diario de transporte`. |
| F27 | Historial de recepciones de María | F20, F23, B35 | Filtros, valor corregido y original; `feat: consultar recepciones`. |
| F28 | Historial y gráficos por vaca | F15, B34 | Cobertura/cero/ausente, período equivalente; `feat: analizar produccion`. |
| F29 | Rectificar/anular producción permitida | F28, B27 | No altera entrega; errores de vínculos; `feat: corregir produccion`. |
| F30 | PDF de producción | F11, F28, B36 | Filtros y advertencia local; `feat: descargar produccion`. |
| F31 | PDF de transporte y recepción | F11, F26, F27, B37 | Ámbito, corte y pendientes; `feat: descargar entregas`. |
| F32 | Resumen administrativo y PDF | F23, F28, B38 | Datos globales, no aprobar por otros; `feat: consultar resumen administrativo`. |
| F33 | Administración de cuentas/roles | F06, B08 | Cambio obligado, desactivación y ámbito; `feat: administrar accesos`. |
| F34 | Catálogos y productos habilitados por centro | F06, B09, B10 | Sin campos de stock ni módulos futuros vacíos; `feat: administrar catalogos`. |
| F35 | Reasignación restringida de receptor | F23, F33, B26 | Solo caso permitido y motivo; `feat: reasignar receptor`. |
| F36 | Notas provisionales y vinculación manual | F11, F19 | No generan firmas ni lotes; `feat: conservar notas de campo`. |
| F37 | Integración logo/ilustraciones y movimiento | F03, F04, F13, F15, F17, F19, F20 | Solo acuse, reducir movimiento; `feat: animar confirmaciones`. |
| F38 | Revisión accesible y adaptación móvil/escritorio | F25–F37 | Teclado, 320 px, zoom, Android real; `fix: ajustar experiencia de campo`. |
| F39 | Prueba integral piloto y mediciones | F38, B40 | Flujo, dos aprobaciones, offline, push y PDF; `test: validar piloto sitrap`. |

La animación puede añadirse después del flujo, pero los recursos se producen explícitamente en F03/F04. La actualización de solicitudes se implementa en F12 y se reutiliza en F19/F20, no se difiere a la última fase.

## 10. Criterios de aceptación de UX

- Producción por vaca → entrega → recogida → recepción sin que Lolo/María vuelvan a escribir litros.
- Guardado local, envío y confirmación central claramente distintos; ningún éxito falso sin acuse.
- María puede aprobar corrección antes de recibir y confirmar recepción después, como acciones diferentes.
- Una sola aprobación nunca cambia cantidad; rechazo/retiro conserva original; no botón de ADMIN para aprobar por otros.
- Mensaje push abre estado actual autenticado; un aviso viejo no confirma versión vieja. Bandeja funciona sin permiso push.
- Calendario e informes reflejan período seleccionado y valores vigentes sin doble conteo; PDF advierte pendientes desde frontend.
- Sin listas vacías de ventas/cuyes/mermas ni formularios de stock en el piloto. Catálogo general permite módulos futuros.
- Pruebas de uso con Vilma/Lolo/María o sus reemplazos: registrar tiempos y pasos, comprensión de estado, éxito en confirmar y recuperarse de desconexión. Indicadores de evaluación en 01 §10.

## 11. Tokens CSS de referencia

Mantener estos nombres como fuente de diseño; conectar Tailwind/componentes sin duplicar colores hardcodeados. La base visual recibida se conserva; ampliaciones cubren tareas de campo y movimiento reducido.


```css
/* SITRAP · Propuesta v2. Interfaz web con tipografía del sistema. */
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --color-primary: #237a57;
  --color-primary-hover: #1b6246;
  --color-on-primary: #ffffff;
  --color-brand-ink: #173d32;
  --color-text: #1d1d1f;
  --color-text-secondary: #515159;
  --color-accent: #f4c95d;
  --color-brand-soft: #eaf5ee;
  --color-background: #f5f5f7;
  --color-surface: #ffffff;
  --color-border-subtle: #d2d2d7;
  --color-border-control: #8e8e93;
  --color-info: #245ea8;
  --color-info-soft: #eaf1fb;
  --color-success: #237a57;
  --color-warning: #805500;
  --color-warning-soft: #fff3cd;
  --color-danger: #b42318;
  --color-danger-soft: #fdece9;
  --color-focus: #245ea8;
  --text-xs: .75rem;
  --text-sm: .875rem;
  --text-base: 1rem;
  --text-card: 1.25rem;
  --text-section: 1.5rem;
  --text-page: 2rem;
  --leading-body: 1.5;
  --space-1: .25rem;
  --space-2: .5rem;
  --space-3: .75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;
  --space-16: 4rem;
  --radius-control: .75rem;
  --radius-card: 1rem;
  --radius-panel: 1.5rem;
  --radius-pill: 999px;
  --control-height: 3rem;
  --target-min: 2.75rem;
  --content-max: 80rem;
  --form-max: 45rem;
  --motion-fast: 150ms;
  --motion-normal: 200ms;
}
@media (max-width: 47.999rem) {
  :root { --text-page: 1.75rem; --text-section: 1.375rem; }
}
@media (prefers-reduced-motion: reduce) {
  :root { --motion-fast: 0ms; --motion-normal: 0ms; }
}
/* Ampliación SITRAP revisión 2: tareas de campo Android. */
:root {
  --color-production-soft: var(--color-brand-soft);
  --color-transport-soft: var(--color-info-soft);
  --color-reception-soft: var(--color-warning-soft);
  --text-quantity: 2.25rem;
  --motion-illustration: 500ms;
}
[data-reduce-motion='true'] {
  --motion-fast: 0ms;
  --motion-normal: 0ms;
  --motion-illustration: 0ms;
}
.quantity { font-variant-numeric: tabular-nums; }
.action-illustration.is-confirmed {
  animation: sitrap-confirm var(--motion-illustration) ease-out 1;
}
@keyframes sitrap-confirm {
  from { transform: scale(.97); opacity: .7; }
  to { transform: scale(1); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  :root { --motion-illustration: 0ms; }
  .action-illustration { animation: none !important; }
}
[data-reduce-motion='true'] .action-illustration {
  animation: none !important;
}
```


Usar variables también en transiciones reales; declararlas no basta. Comprobar contraste final de cada combinación y feedback en teléfonos del piloto.

## 12. Preparación para diseño en Figma

Cuando se solicite: páginas Fundamentos, Componentes, Producción, Transporte, Recepción, Administración, Avisos y Estados offline. Referencias móviles 360–412 px y escritorio 1440 px, comprobando reflujo a 320 px. Prototipos: flujo normal; modificación antes de recogida; corrección con dos aprobaciones antes/después de recepción; push denegado/activo; sesión vencida con pendientes.

Entregar componentes/tokens, textos y navegación por roles, con variantes carga/error/vacío/pendiente local. La vaca es mascota del módulo leche, no sustituye la identidad genérica. Estos archivos especifican el diseño; no crean todavía un archivo Figma.

Referencias: [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [Movimiento reducido](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion), [Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API), [Notificaciones](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API), [PWA offline y background](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation). La sincronización del piloto se realiza en primer plano y no depende de Background Sync.
