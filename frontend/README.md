# SITRAP frontend

Requiere Node 24 LTS y npm. Desde `frontend/`: `npm ci`, `npm run dev`.
Verificación: `npm test` y `npm run build`.

En `integracion-mvp`, HTTP real es el modo predeterminado. `VITE_API_MODE=mock`
habilita exclusivamente la demostración local. Vite redirige `/api/v1` a
`VITE_API_PROXY_TARGET` (por defecto `127.0.0.1:8000`), sin CORS ni credenciales
entre dominios. Ejecución y límites reales: [README raíz](../README.md) y
[integración](../docs/INTEGRACION_MVP.md). `../docs/AVANCE_FRONTEND.md`
describe solo el estado previo de la rama separada.
