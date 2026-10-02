# Avisos internos y Web Push

La bandeja funciona aunque PUSH_ENABLED=False. No es necesario aceptar push para operar.
Las suscripciones se crean únicamente tras el gesto y consentimiento del usuario en
el frontend. El backend no concede ni simula ese permiso.

GET /api/v1/push/config devuelve enabled y vapid_public_key, nunca la privada.
POST /push/subscriptions recibe {device_id,endpoint,keys:{p256dh,auth}}.
El frontend selecciona esos campos de PushSubscription.toJSON(); no manda actores.
Respuesta y listado contienen id/dispositivo/fechas/activo, sin endpoint ni claves.
Repetir endpoint propio actualiza sus claves y reactiva la suscripción sin duplicar.
Un endpoint de otra cuenta/dispositivo exige desuscribir en el navegador y obtener
una suscripción nueva; no se transfiere silenciosamente.

GET /push/subscriptions y DELETE /push/subscriptions/{id} usan X-Device-ID.
El listado está paginado. DELETE desactiva y es idempotente. Logout recibe
X-Device-ID (o usa el dispositivo asociado al registro/suscripción de esa sesión)
y desactiva suscripciones del dispositivo antes de revocar la sesión. La baja de
cuenta desactiva todas las suyas. El frontend debe resolver su cola antes del logout.

PUSH_ALLOWED_HOSTS delimita proveedores HTTPS permitidos; no admite URLs arbitrarias
ni destinos internos. Valores iniciales: FCM, Mozilla, Apple y subdominios
notify.windows.com. Revisar explícitamente la lista si un navegador usa otro proveedor.
No registrar endpoint, claves, contenido de excepciones del proveedor ni payload sensible.

## Preparar VAPID sin publicar secretos

Con PUSH_ENABLED=False, ejecutar localmente:
```powershell
.\.venv\Scripts\python.exe manage.py generate_vapid --output .local/vapid.env --subject mailto:contacto@su-dominio
```
El comando exige archivo nuevo y no imprime la privada. En Windows restringir ACL
del archivo al usuario/servicio; en Linux se crea con modo 0600. Importar esas variables
al entorno protegido (no se cargan automáticamente desde .local/vapid.env).
PUSH_ENABLED=True exige claves P-256 coincidentes y un contacto VAPID.
La privada usa DER PKCS8 en base64url; la pública, punto P-256 sin comprimir en base64url.
Conservar el mismo par entre despliegues; cambiarlo requiere renovar suscripciones.

Biblioteca fijada: [pywebpush 2.5.0](https://pypi.org/project/pywebpush/2.5.0/);
contrato de envío y VAPID consultado en el [repositorio oficial](https://github.com/web-push-libs/pywebpush).
B32 agrega outbox transaccional; B33 agrega worker y reintentos. Se verificó cifrado/descifrado aes128gcm y carga de clave VAPID con la biblioteca
fijada. No se han realizado envíos reales a teléfonos; la aceptación por un proveedor no prueba lectura.

B32: outbox durable PushDelivery, UNIQUE(notification,subscription), creada con
el hecho y aviso. Payload genérico: notification_id/tag estable, title, body, url=/.
El Service Worker muestra el aviso; no confirma recogida, recepción ni corrección.
