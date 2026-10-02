# SITRAP · integración local del MVP

La rama `integracion-mvp` reúne Django/DRF y la PWA React. **No es un despliegue**.
La API real es el modo predeterminado (`VITE_API_MODE=http`); el modo `mock`
solo sirve para demostraciones/pruebas aisladas. Las cuatro especificaciones
`SITRAP_0*.md` siguen siendo la fuente de reglas de negocio.

### Arranque local (Windows, PowerShell)

Requiere Python 3.12, PostgreSQL 18, Node 24 y npm. Desde la raíz:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.txt
.\scripts\local-postgres.ps1 Start -Port 55433
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_admin --username admin-local --name "Administración local"
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`local-postgres.ps1` crea `.env` solo si no existe; si el puerto 55433 está ocupado,
elige otro con `-Port` y conserva el `DATABASE_URL` correspondiente. Prepara cuentas,
roles, ámbitos, catálogo de leche, presentación de bolsa y estancias de vacas en la
base local antes de usar el flujo. No reutilices datos ni credenciales de producción.
En otra consola:

```powershell
cd frontend
npm ci
npm run dev
```

Abrir `http://localhost:5173`; **no** abrir la interfaz directamente por el puerto
8000. Vite reenvía `/api/v1` al backend y conserva el mismo origen para las cookies
de sesión y CSRF; no hace falta CORS. Si Django usa otro puerto, configurar
`frontend/.env.local` con `VITE_API_PROXY_TARGET=http://127.0.0.1:<puerto>`.
`frontend/.env.example` documenta las variables públicas. `.env` de la raíz
requiere `DEBUG`, `SECRET_KEY`, `DATABASE_URL` y `ALLOWED_HOSTS`; opciones:
`CSRF_TRUSTED_ORIGINS`, `SESSION_COOKIE_AGE`, `OFFLINE_PREPARATION_DAYS`,
`PUSH_ENABLED` y claves VAPID según `docs/PUSH.md`. No comitear secretos.
Para PDF en Windows, consultar `docs/REPORTS.md` y configurar
`WEASYPRINT_DLL_DIRECTORIES` en `.env` después de preparar el runtime.

En la aplicación, ingresar con cada cuenta asignada, ir a **Sincronización →
Preparar dispositivo** con conexión y renovar la preparación antes de su vencimiento.
Las operaciones offline se conservan por cuenta y se envían con la misma intención.

Pruebas: `npm test`, `npm run build` y `npm run test:e2e` desde `frontend/`.
Backend: `.\.venv\Scripts\python.exe -m pytest -q --basetemp .local/pytest-temp`
y `.\.venv\Scripts\python.exe -m ruff check .` desde la raíz. PostgreSQL real
es obligatorio; los PDF necesitan las DLL de WeasyPrint en Windows.

Ver [docs/INTEGRACION_MVP.md](docs/INTEGRACION_MVP.md) para el alcance de
verificación y las limitaciones que impiden afirmar aceptación en Android.

## Backend (referencia original)

Implementación incremental de los cuatro documentos SITRAP, revisión 3.
Trabajo exclusivamente en `agente-backend`. Estado: [docs/AVANCE_BACKEND.md](docs/AVANCE_BACKEND.md).

Python 3.12 y Django 5.2 LTS con PostgreSQL real. Crear un entorno virtual,
instalar `requirements-dev.txt`, copiar `.env.example` a `.env` y configurar la BD.
No se admite SQLite para desarrollo ni pruebas.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver
```

API bajo `/api/v1`, sin barra final. `GET /api/v1/health` comprueba el proceso
sin depender de BD. OpenAPI: `/api/v1/schema`; copia versionada en `docs/openapi.yaml`.

Actualizar dependencias explícitamente, regenerar ambos locks con pip-compile,
ejecutar pruebas y revisar el diff antes de confirmar. Las versiones compatibles
se resuelven desde PyPI; Django 5.2 es LTS según
[Django](https://docs.djangoproject.com/en/5.2/releases/5.2/).

Aplicar migraciones con `python manage.py migrate` (usuario personalizado disponible).

Pruebas PostgreSQL y CI: [docs/PRUEBAS.md](docs/PRUEBAS.md).
Para regenerar locks de desarrollo usar `pip-compile --allow-unsafe --generate-hashes`.


## Actualizar dependencias

Usar el índice HTTPS esperado y conservar hashes:

```powershell
.\.venv\Scripts\python.exe scripts/compile_locked.py --generate-hashes --allow-unsafe --strip-extras --index-url https://pypi.org/simple --output-file requirements.txt requirements.in
.\.venv\Scripts\python.exe scripts/compile_locked.py --generate-hashes --allow-unsafe --strip-extras --index-url https://pypi.org/simple --output-file requirements-dev.txt requirements-dev.in
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.txt
```

El helper usa SHA-256 anunciado por el índice Simple, como pip-tools hace con la API
JSON; si falta, descarga y calcula. Evita descargar ruedas de todas las plataformas
cuando la API JSON no devuelve hashes. La instalación verifica los artefactos contra
el lock; `pip download --require-hashes -r requirements.txt --dest .local/verified-wheels`
permite verificar también paquetes ya instalados. No modifica pip-tools instalado.

Avisos al teléfono: [configuración VAPID y contrato](docs/PUSH.md).
Sincronización: [protocolo de caché/cursores/eventos](docs/SYNC_PROTOCOL.md).
