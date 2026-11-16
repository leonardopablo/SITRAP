# Verificación local · Cuyes Etapa 2

Fecha: 16 de noviembre de 2026. Rama: `feat/cuyes-etapa-2`.
Base de trabajo: commit de Etapa 1 `b5d1627`. Sin despliegue ni fusión a `main`.

## Resultado de ejecución

| Comprobación | Resultado |
|---|---|
| Pytest completo con PostgreSQL real y `SITRAP_BROWSER_TESTS=1` | **224 aprobadas**, sin pruebas omitidas |
| Recorrido real Etapa 1: móvil → Django → PostgreSQL | Aprobado; incluido en pytest |
| Recorridos reales Etapa 2: módulo/PIN y peso/conductor/punto/cliente | Aprobados; incluidos en pytest |
| Ruff | Correcto |
| Django `check` | Sin incidencias |
| `makemigrations --check --dry-run` | Sin cambios pendientes |
| `migrate --check` | Sin migraciones pendientes |
| OpenAPI generado con `--validate --fail-on-warn` | Correcto, sin advertencias |
| Contrato versionado contra generado | Aprobado en pytest |
| `npm run api:generate` | Tipos regenerados |
| `npm test` | **71 aprobadas**, 41 archivos |
| `npm run test:e2e` | **33 aprobadas**, regresión existente con mock explícito |
| `npm run build` | Correcto |
| `git diff --check` | Sin errores de whitespace |

Los E2E con mock no se presentan como evidencia de integración real: esta última
usa live_server, Vite y una base PostgreSQL temporal, con cuentas/datos ficticios
y las API reales de sesiones, CSRF, comprobantes, PIN, reserva y Kardex.

Se probaron componentes escasos, competencia entre órdenes, reservas atómicas,
pago frente a vencimiento, expiración idempotente, diferencia de peso pospago,
PIN incorrecto/correcto/regenerado/consumido, límites de intentos y reintentos.
También: selección competida, múltiples galpones y lotes, conformidades
invalidadas, salida concurrente con descuento único, entrega posterior sin
descuento adicional, faltante por mortalidad, permisos y comprobantes privados.
La suite conserva regresión del piloto de leche y del inventario de Etapa 1.

## Cambios y migraciones aplicadas

- Reutilización de Occupation, Balance, CuyLot, Movement y LedgerLine.
- Bloqueo de centro compartido entre operaciones físicas y comerciales.
- Detección transaccional de faltantes sin impedir registrar una muerte.
- Modelos comerciales propios: módulos/componentes, órdenes/líneas, reservas,
  evidencia/pago, revisiones económicas, propuestas, preparación/selección,
  conformidades, despacho/detalle, entregas y revisiones.
- API online, proyecciones por espacio de trabajo y permisos de origen/conductor.
- PIN fuera del payload persistido de SyncOperation; hash, consumo atómico y
  contador de intentos. Evidencia en almacenamiento privado, no bajo una URL media.
- Bandeja/outbox reutilizadas y comando de vencimiento por lotes.

Migraciones cuyes:

1. **0004:** modelos comerciales, relaciones y restricciones de cantidades,
   reserva activa, unicidad de pago/despacho y conformidades.
2. **0005:** triggers append-only de evidencia y hechos comerciales/logísticos.
3. **0006:** restricción de estados conocidos de orden.
4. **0007:** longitud de referencia para conservar la resolución administrativa
   completa de un pago al cancelar.

No hay migración de saldos, usuarios, centros, módulos o precios ficticios.

## Base de uso local

Respaldo anterior a migrar:
`.local/backups/before-cuyes-20261116-163132.dump` (ignorado por Git).

| Datos locales | Antes | Después |
|---|---:|---:|
| Ordeños | 8 | 8 |
| Lotes de leche | 7 | 7 |
| Entregas de leche | 12 | 12 |
| Movimientos de cuyes | 0 | 0 |
| Saldos de cuyes | 0 | 0 |
| Órdenes/pagos de venta | No existían las tablas | 0 / 0 |

Las cuatro migraciones se aplicaron a PostgreSQL local. No se modificó `.env`,
no se instaló un cron/tarea y no se tocaron datos de producción.
Después de empezar a usar comprobantes, el respaldo debe incluir también el
directorio privado además de PostgreSQL.

## Incidencias intermedias y límites

- El PostgreSQL local iniciado mediante un proceso desacoplado dejó de responder.
  Se reinició como proceso local persistente y se repitió la suite completa:
  el resultado final fue 224 aprobadas.
- Hubo una colisión de archivos al ejecutar dos compilaciones sobre `dist`
  simultáneamente. Se repitió la compilación por separado y terminó correctamente.
- Vite sigue avisando de un chunk principal mayor de 500 kB y de la opción
  `inlineDynamicImports` del plugin PWA; no impiden compilar. Ventas es un chunk
  separado, cargado bajo demanda.
- No se verificaron Android físico, Web Push real, antivirus ni infraestructura
  de respaldos/planificación de producción. La guía describe cómo programar el
  vencimiento, pero no instala servicios.
- Las categorías comerciales habilitadas son MACHO y HEMBRA; lactantes sin sexar
  deben destetarse/sexarse antes de la venta.
- El peso vivo/beneficiado es un dato declarado para el cobro, no un módulo de
  faenado. Pagos, cobros adicionales y devoluciones económicas son verificados
  manualmente: no hay pasarela, devolución física ni documento fiscal.

Guía de configuración y recorridos manuales:
[CUYES_ETAPA2.md](CUYES_ETAPA2.md).
