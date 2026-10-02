# SITRAP backend

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
