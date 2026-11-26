# Dirección DIPROBSA e historial de demostración

## Abrir la demostración

La base PostgreSQL original `sitrap` y sus comprobantes **no se reemplazan**. El
generador local hace un respaldo y restaura un clon `sitrap_demo_YYYYMMDD_HHMMSS`.
Solo reconstruye los datos operativos del clon. Se conservan cuentas,
contraseñas, roles y asignaciones; se reconstruyen los permisos por galpón.
Sesiones, dispositivos, notificaciones y suscripciones Push se aíslan del original.
No subas los respaldos, las credenciales ni las bases de demostración a GitHub.

```powershell
.\.venv\Scripts\python.exe scripts/create_direction_demo.py
.\.venv\Scripts\python.exe scripts/serve_direction_demo.py sitrap_demo_YYYYMMDD_HHMMSS
```

Usa el nombre exacto que imprima el primer comando. En otra terminal:

```powershell
cd frontend
$env:VITE_API_MODE = 'http'
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8002'
$env:VITE_SITRAP_DEMO = '1'
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Abre `http://127.0.0.1:5174`. No uses esa pestaña para datos reales: el frontend
de demostración tiene otro origen y Django usa cookies de demo. La interfaz habitual
mantiene su propia configuración.

Para revalidar el clon recién creado, antes de crear cuentas nuevas en él:

```powershell
.\.venv\Scripts\python.exe scripts/verify_direction_demo.py sitrap_demo_YYYYMMDD_HHMMSS
```

El verificador compara las cuentas y asignaciones con la base original, concilia
los saldos con el Kardex, y revisa el enlace entre despachos y retiros. El rol de
Dirección se incorpora mediante `accounts.0006_director_role`; aplicar esa
migración en otro entorno no genera registros de demostración.

## Acceso y prueba manual

1. Ingresa con ADMIN y crea una cuenta de Dirección en **Cuentas**. Selecciona el
   rol `DIRECTOR` en **Asignar función**; la asignación es global, sin ubicación.
2. En otro perfil, entra con la cuenta nueva y cambia la contraseña temporal.
   Debe abrir **Dirección DIPROBSA**. ADMIN también puede abrir la vista desde **Hoy**.
3. Selecciona el período iniciado el 1 de enero de 2026 y filtra Kotosh: comprueba
   12 vacas, producción por vaca, 2 galpones y 1.500 cuyes al cierre del día previo.
4. Filtra Canchán: debe aparecer un galpón, 1.500 cuyes y leche **No aplica**.
5. Expande las trazas de ventas de cuyes y de leche. Verifica lotes, destino,
   fechas y responsables. El rol no accede a Cuentas, comprobantes ni cambios
   operativos. Si ADMIN finaliza la asignación, la API deja de permitir la consulta.

## Cómo leer los indicadores

- Los gráficos se alimentan de datos confirmados de PostgreSQL, no de una tabla
  de totales manual. El panel consulta cada minuto mientras está abierto y
  ofrece el botón **Actualizar indicadores**.
- El saldo de cuyes es el saldo del Kardex al día de corte. Natalidad y
  mortalidad usan nacidos vivos o muertes netas por 100 cuyes de población media
  diaria; no se calculan si hubo pozas abiertas durante el intervalo y falta una
  base comparable. Natimortalidad usa nacidos totales como denominador.
- Los litros producidos se leen de la versión publicada del ordeño no anulado.
  Recogida y recepción son hechos fechados; la diferencia compara cantidades de
  la misma entrega, no resta totales de viajes distintos.
- Los pagos mostrados son importes originales validados, separados por moneda;
  no representan utilidad ni ingresos netos de devoluciones.
- Los pendientes y alertas reflejan el estado actual. Las cifras de actividad
  corresponden al período seleccionado. Son conteos de trabajo y no una
  calificación del personal.

La leche usa el recorrido existente, que exige conductor y receptor. El recojo
directo sin conductor corresponde a **ventas de cuyes**. La demostración no
introduce un flujo nuevo de transporte de leche.
