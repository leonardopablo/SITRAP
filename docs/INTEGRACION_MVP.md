# Integración MVP: verificación y límites

Las ramas `agente-backend` y `agente-frontend` se fusionaron desde `main`,
conservando las exclusiones de Python y Node. La rama frontend anterior era un
mock explícito; ahora HTTP es predeterminado y el cliente usa rutas relativas
`/api/v1` detrás del proxy Vite. El esquema ejecutable del servidor se copia a
`frontend/src/api/backend.generated.d.ts` mediante `npm run api:generate`.
`frontend/src/api/generated.d.ts` sigue describiendo el modelo provisional del
mock: no usarlo como evidencia de coincidencia de contratos en módulos restantes.
El proxy de desarrollo preserva `Host` para que la comprobación CSRF de Django
compare el mismo origen que usa el navegador en `localhost:5173`; no se desactiva
CSRF ni se necesita volver a migrar para solucionar un rechazo de login.

Si se finalizó el único rol ADMIN, la cuenta seguirá pudiendo autenticarse pero
`/auth/me` ya no mostrará funciones. No reabrir la asignación histórica ni borrar
su auditoría. Un operador con acceso local a la BD puede crear una asignación
nueva y auditada, únicamente si no queda ningún ADMIN activo:
`python manage.py recover_admin --username admin-local --confirm-no-admin`.
Hay que salir de la sesión y volver a entrar para renovar `/auth/me`. La API y
la interfaz ahora rechazan que un administrador finalice su propia asignación o
desactive su propia cuenta; la API también protege al último ADMIN.

Verificación local: una prueba pytest con usuarios autenticados de producción,
transporte y recepción crea y envía una entrega sobre un lote confirmado, comprueba
el aviso a transporte, confirma recogida sin cambiar litros, comprueba el aviso a
recepción, confirma recepción y consulta el mismo documento con los tres usuarios.
Prueba API/BD real, **no** una sesión completa de navegador con teléfonos.
Se probaron adicionalmente captura local, sincronización y PWA con tests frontend
en mock; todavía no hay prueba automatizada navegador→Django de todo el recorrido.

Pendiente antes de piloto: ensayo en Android de instalación, push real (requiere
VAPID/worker/HTTPS), desconexión/reconexión y expiración con personas y red reales;
confirmar nombres institucionales, turnos y asignaciones. Los listados paginados
no tienen aún navegación de páginas en todas las pantallas (p. ej. vacas, entregas,
avisos); no asumir que se ven todos los registros de un centro grande. Las rutas
administrativas y pantallas secundarias necesitan prueba de navegador contra Django
antes de la aceptación del piloto. B40/despliegue y restauración siguen pendientes.

No inferir stock, merma o venta de la diferencia entre producido y entregado.
