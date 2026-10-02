# SITRAP backend

Implementación incremental de los cuatro documentos SITRAP, revisión 3.
Trabajo exclusivamente en `agente-backend`. Estado: [docs/AVANCE_BACKEND.md](docs/AVANCE_BACKEND.md).

Python 3.12 y Django 5.2 LTS con PostgreSQL real. Crear un entorno virtual,
instalar `requirements.txt`, copiar `.env.example` a `.env` y configurar la BD.
No se admite SQLite para desarrollo ni pruebas.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
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

No ejecutar migraciones del proyecto B01 sobre una BD persistente hasta añadir el
usuario personalizado (B03), para evitar crear sesiones/auth con un usuario equivocado.
