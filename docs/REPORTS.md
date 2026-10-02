# Métricas e informes

Todas las rutas requieren sesión vigente y permisos actuales. date_from/date_to
son fechas inclusivas America/Lima, con máximo 366 días y 10.000 registros por
conjunto. REPORT_TOO_LARGE exige reducir período/filtros. No hay truncamiento
silencioso. Cada cálculo usa una fotografía PostgreSQL REPEATABLE READ.

- GET /api/v1/metrics/milk: P de sus centros o ADMIN. Filtros center_id, product_id,
  animal_id, turn_id. Solo versión confirmada vigente, excluye borrador/anulación.
  Cero cuenta como registro; un día sin registro tiene liters=null. El promedio
  divide por días con registro. days_present usa estancias históricas, no estado
  activo actual ni supuesta lactancia. Filtrar turno cambia los registros, sin
  afirmar que debió ordeñarse en todos los turnos.
- GET /api/v1/metrics/transfers: mismos ámbitos que las entregas. Filtros center_id
  (origen), destination_id, product_id. Recogido y recibido separados por fecha
  física; cantidad documental vigente y corrected cuando hubo corrección aplicada.
- GET /api/v1/reports/production.pdf: mismos filtros/ámbitos que metrics/milk.

PDF devuelve application/pdf, Content-Disposition attachment y Cache-Control
private,no-store. Plantilla controlada y texto escapado; sin recursos de red,
archivos locales ni HTML proporcionado por cliente. Incluye filtros y corte del
servidor. El frontend advierte sus pendientes locales antes de descargar; el
servidor no puede comprobarlos. Requiere conexión.

## Motor PDF

WeasyPrint 70.0 fijado y dependencias con hashes. Linux:
`apt-get install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core`.
La CI ya prepara esas bibliotecas.

Windows: `python scripts/setup_pdf_windows.py` descarga el runtime onedir oficial
v70.0 en .local/weasyprint70 y verifica SHA-256. Configurar en .env (ruta absoluta):
`WEASYPRINT_DLL_DIRECTORIES=<repo>/.local/weasyprint70/onedir/weasyprint/_internal`.
No instala servicios ni altera PATH global. Alternativa: MSYS2/Pango según la
[documentación oficial](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).
La [publicación 70.0](https://github.com/Kozea/WeasyPrint/releases/tag/v70.0) incluye
el runtime y correcciones de seguridad.

Pruebas generan PDF real y extraen texto con pypdf. PDF_QA_DIR=.local/pdf-qa permite
guardar muestras para renderizar con Poppler y revisar visualmente; esas muestras
son datos de prueba ignorados por Git. Se revisaron el informe normal y las cuatro
páginas de una tabla de 100 filas, sin cortes ni solapamientos.

B37: /reports/transfers.pdf permite P del origen, T propio o A;
/reports/receptions.pdf permite R propio o A. Ambos usan filtros de
metrics/transfers y muestran cantidades vigentes/corregidas y fechas fisicas.
Recepciones incluye solo recepciones fisicas dentro del periodo.

B38: /metrics/overview y /reports/overview.pdf exclusivos ADMIN; filtros
date_from/date_to/center_id/product_id. Misma fotografia y corte para produccion
y entregas; resumen por centro de origen sin sumar las tres medidas.
