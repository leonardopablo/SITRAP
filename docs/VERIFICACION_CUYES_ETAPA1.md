# Verificación local · Cuyes Etapa 1

Fecha: 16 de noviembre de 2026. Rama: `mejora/iteracion-2`.
Sin despliegue, sin datos de producción y sin fusión a `main`.

| Verificación ejecutada | Resultado |
|---|---|
| Pytest completo con PostgreSQL real y `SITRAP_BROWSER_TESTS=1` | **194 aprobadas**, incluidas concurrencia, leche y navegador real |
| Ruff | Correcto |
| `manage.py check` | Sin incidencias |
| `makemigrations --check --dry-run` | Sin cambios pendientes |
| `migrate --check` | Sin migraciones pendientes |
| OpenAPI generado, validado y comparado en pytest | Correcto, sin advertencias |
| `npm run api:generate` | Tipos regenerados |
| `npm test` | **67 aprobadas**, 40 archivos |
| `npm run build` | Correcto |
| `npm run test:e2e` | **33 aprobadas**, regresión existente con mock |
| Recorrido móvil navegador → Django → PostgreSQL sin mock | Aprobado; incluido en las 194 de pytest |
| `git diff --check` | Sin errores de whitespace |

El recorrido real verificó login por sesión/CSRF, acceso directo de GALPONERO,
apertura física, preparación del dispositivo, nacimiento vivo/natimorto,
mortalidad, destete repartido, conteo, cierre, reapertura administrativa y ajuste.
Las pruebas de cola simulan pérdida de respuesta, UUID estable, conflicto de saldo,
revocación y bloqueo de cierre hasta revisar intenciones.

Se comprobaron competencias entre cuentas por saldo, capacidad y cierre, y
recepción concurrente. Una consulta de un movimiento compartido filtra líneas y
payload tras revocar un galpón. Bootstrap/changes comprueba tombstones y descarte de
páginas incompletas por cambio de ámbito.

## Base local y conservación de leche

Se respaldó la base local antes de aplicar cinco migraciones nuevas:
accounts 0004–0005 y cuyes 0001–0003.

Respaldo ignorado por Git:
`.local/backups/before-cuyes-20261116-131514.dump`.

Comprobación anterior y posterior a migrar:

| Dato local | Antes | Después |
|---|---:|---:|
| Ordeños | 8 | 8 |
| Lotes de leche | 7 | 7 |
| Entregas de leche | 12 | 12 |

Al entregar, la base de uso local tiene **0 movimientos y 0 saldos de cuyes**.
Los ejemplos del navegador se crearon exclusivamente en la base temporal de
pytest. No se crearon centros duplicados ni saldos basados en estimaciones.

## Advertencias y límites de la verificación

- Vite informa un chunk principal mayor a 500 kB y deprecación de
  `inlineDynamicImports` del plugin PWA; la compilación termina correctamente.
  Cuyes se carga en un chunk separado.
- Durante verificaciones intermedias PostgreSQL local dejó de responder; se
  reinició el clúster local y se repitieron las comprobaciones satisfactoriamente.
- No se probó instalación/PWA ni Web Push en un Android físico. Eso requiere
  dispositivos reales, HTTPS y configuración VAPID/worker del proyecto.
- La evaluación de alertas de antigüedad/rendimiento se activa desde el tablero;
  no se instala un scheduler de infraestructura.
- El reconocimiento de un rechazo en el teléfono es una anotación local con
  motivo: no aplica inventario, no aprueba ajustes y no sustituye la reapertura.

Guía funcional, cálculo de indicadores, API y comandos reproducibles:
[CUYES_ETAPA1.md](CUYES_ETAPA1.md).
