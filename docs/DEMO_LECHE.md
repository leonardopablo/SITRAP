# Datos demo de leche (B39)

Solo en una base **de desarrollo** con `DEBUG=True`. Nunca ejecutar sobre datos reales.
Con PostgreSQL local arrancado y las migraciones aplicadas:

```powershell
.venv/Scripts/python.exe manage.py seed_milk_demo --confirm-demo --date 2026-10-01
```

El comando exige `DEBUG=True` y `--confirm-demo`, rechaza códigos/usuario ya usados
y no modifica una demo existente. Crea un centro, un producto en litros habilitado,
dos vacas con estancia, un turno, un operador con contraseña inutilizable y un
dispositivo. Registra mediante los mismos comandos auditados que la API un ordeño
confirmado de **5.500 L** (2.500 + 3.000) y su lote. El resultado imprime los UUID
para consultar `/api/v1/milkings/{id}` y filtrar `/api/v1/metrics/milk` por fecha y
centro. Para probar la interfaz con inicio de sesión, crear cuentas de prueba por
los mecanismos habituales; el operador sembrado no puede iniciar sesión.

La fecha se especifica explícitamente para que la demo sea reproducible. No hay
entrega ni recepción física simulada: esas métricas serán cero. Ejecutar la demo
en una base desechable; no hay comando de borrado porque debe conservarse la
trazabilidad y el registro de auditoría.

Contrato del piloto: `docs/openapi.yaml` se genera desde las rutas y serializadores
implementados con `manage.py spectacular`; `tests/test_pilot_contract.py` detecta
desviaciones respecto al esquema generado. `scripts/check.ps1` valida el esquema,
el código y las pruebas contra PostgreSQL real.
