# Pruebas del backend

Usar Python 3.12, el lock `requirements-dev.txt` y PostgreSQL 18.
Nunca apuntar DATABASE_URL de pruebas a producci?n. pytest-django crea y destruye
su propia base `test_sitrap` aplicando todas las migraciones. El usuario local/CI
necesita CREATEDB; el futuro usuario de aplicaci?n en producci?n no.

## Windows

`scripts/local-postgres.ps1 Start` crea un cl?ster privado con contrase?a aleatoria
en `.local/pgdata` y puerto 55432. Usa binarios PostgreSQL instalados, no cambia el
servicio de Windows ni otras bases. Mantener el mismo usuario de Windows para
inicializar y arrancar. `Stop` detiene exclusivamente ese cl?ster.

`scripts/check.ps1` ejecuta checks, verifica migraciones, pytest, Ruff y OpenAPI.
Para una prueba: `.venv/Scripts/python.exe -m pytest tests/test_postgres.py -v`.

## CI

`.github/workflows/backend.yml` prepara PostgreSQL real, instala dependencias
bloqueadas y ejecuta migraci?n limpia, tests y verificaci?n del contrato.
Una configuraci?n de CI presente no significa ejecuci?n remota verificada.

## Concurrencia

Las pruebas de carreras usan conexiones/hilos separados y
`pytest.mark.django_db(transaction=True)`, con barreras y timeouts. No sustituir
por SQLite ni por un ?nico TestCase que serialice accidentalmente los comandos.
