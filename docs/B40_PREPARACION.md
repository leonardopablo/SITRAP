# B40: preparación operativa (sin despliegue)

**Estado:** configuración e instrucciones preparadas; no se creó ningún recurso
Azure, no se restauró backup remoto, no hay frontend integrado ni aceptación en
dispositivos reales. B40 no está terminada. Antes de activar el piloto, definir
región, tamaños, costos, responsables, dominio y política de retención con el equipo.

## Topología y configuración

- Web Django: proceso WSGI/ASGI supervisado detrás de proxy HTTPS; frontend compilado
  y Service Worker en **el mismo origen**. Azure App Service es una opción, no una
  configuración ya aplicada. Servir `/api/v1/` desde Django y `/` desde el frontend;
  no enviar `/api/v1/` a la SPA. Configurar estáticos y dependencias nativas de
  WeasyPrint/fonts en la imagen elegida, comprobando PDFs antes de aceptar tráfico.
- Worker: proceso continuo separado (p. ej. Azure Container Apps con réplica mínima
  1, sin escala a cero) del **mismo commit**, ejecutando
  `python manage.py push_worker`. Web y worker comparten PostgreSQL, secretos y
  VAPID; el worker requiere salida HTTPS a proveedores push. Supervisar reinicios.
- Base: PostgreSQL Flexible Server con TLS y acceso privado restringido; cuenta de
  aplicación no propietaria, sin DDL/TRUNCATE sobre tablas auditadas; identidad
  separada y temporal para migraciones/backup. Probar permisos con esa cuenta.
- Secretos protegidos fuera de Git: `SECRET_KEY` robusta, `DATABASE_URL` con TLS,
  `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT`; web y worker comparten
  los mismos valores. `.env.example` solo documenta nombres, no credenciales.
  Configurar `DEBUG=False`, `ALLOWED_HOSTS` exactos, `CSRF_TRUSTED_ORIGINS` HTTPS,
  `PUSH_ENABLED=True` solo con VAPID estable, y revisar `PUSH_ALLOWED_HOSTS`.
  Rotar claves VAPID implica renovar suscripciones de navegadores.
- El proxy debe transmitir la IP real mediante una integración **verificada**;
  hoy el límite de login usa `REMOTE_ADDR` e ignora `X-Forwarded-For`. Si todos los
  usuarios aparecen con la IP del proxy, no activar tráfico real sin resolver el
  ajuste con un proxy de confianza explícito; nunca confiar en cabeceras del cliente.

## Orden de puesta en marcha futuro (no ejecutar todavía)

1. Integrar frontend, origen HTTPS, cookies Secure/CSRF y Service Worker; probar
   login, permisos, cola offline, PDF y Web Push en dispositivos reales.
2. Crear infraestructura y secretos mediante el procedimiento aprobado. Ejecutar
   `python manage.py check --deploy`, probar TLS/ACL, e instalar exactamente
   `requirements.txt` con hashes. Aplicar `python manage.py migrate` **una vez**
   mediante identidad de migración, nunca en cada réplica web/worker. Crear el
   primer ADMIN con `bootstrap_admin` y contraseña temporal fuera de logs.
3. Iniciar web y worker supervisados. Verificar `GET /api/v1/health` (solo confirma
   proceso web), `python manage.py push_status --max-age 120` (latido/cola), y
   métricas de errores 401/403/409/422, cola retrasada, 429/5xx y reinicios.
   No interpretar `ACEPTADO_PROVEEDOR` como notificación leída.
4. Programar `python manage.py prune_sync_snapshots` para inspección y luego
   `python manage.py prune_sync_snapshots --apply --batch-size 500` periódicamente.
   Solo borra `SyncSnapshot` vencidos; conserva `SyncOperation`, dependencias,
   auditoría y datos de negocio. Verificar volumen, índices y tiempo en la base
   elegida antes de programar la frecuencia/retención. Las cubetas de login
   caducadas requieren política propia antes de producción.

## Backup y restauración (ensayo pendiente)

Definir retención y cifrado de backups automáticos PostgreSQL y exportación
periódica con `pg_dump` a almacenamiento protegido, acceso restringido y claves
separadas. Registrar hora/versión de esquema/commit y prueba de lectura. Para cada
ensayo: restaurar en **instancia aislada**, con secretos distintos y `PUSH_ENABLED=False`
para evitar avisos a dispositivos reales; aplicar migraciones compatibles solo
tras verificar versión. Comprobar integridad de auditoría, recuentos de operaciones,
consultas e informes, y medir RPO/RTO. No restaurar sobre producción ni reenviar
cola push de una copia. Los pasos concretos y tiempos solo podrán declararse
validados cuando exista un backup real y un ensayo firmado.
