import { Link } from 'react-router-dom'
import type { Role } from '../api/types'
import { roleLabels, useWorkspace } from '../auth/workspace'
import { Notice } from '../components/ui'

type Guide = { title: string; summary: string; to?: string; steps: string[]; caution?: string }

const guides: Record<Role, Guide[]> = {
  DIRECTOR: [{ title: 'Panel de Dirección', summary: 'Consulta de indicadores confirmados.', to: '/direccion', steps: ['Selecciona el período y el centro.', 'Revisa los indicadores y su trazabilidad.'], caution: 'El acceso es de solo lectura.' }],
  GALPONERO: [{ title: 'Inventario de cuyes', summary: 'Trabajo por galpón, poza y lote.', to: '/cuyes', steps: ['Selecciona tu galpón y la poza.', 'La apertura sale del conteo físico, nunca de una cifra estimada.', 'Registra nacimientos y mortalidad; sin conexión se guardan como pendientes.', 'Destetes, traslados y conteos requieren conexión.', 'Sincroniza y revisa rechazos antes de cerrar el parte, incluso con cero novedades.'], caution: 'El saldo confirmado no incluye novedades pendientes de otros teléfonos.' }],
  PRODUCCION: [
    { title: 'Hoy', summary: 'Reúne los accesos para comenzar el trabajo del día.', to: '/hoy', steps: ['Comprueba que aparezcan tu nombre, Producción y el centro correcto.', 'Entra a registrar el ordeño o a preparar una entrega desde los enlaces de la pantalla.'] },
    { title: 'Registrar producción', summary: 'Registra los litros obtenidos de cada vaca y crea el lote del ordeño.', to: '/produccion', steps: ['Selecciona el turno correcto; la fecha corresponde al día actual en Perú.', 'Escribe los litros de cada vaca. Deja vacío solo si no conoces el dato; escribe 0 cuando produjo cero litros.', 'Guarda el borrador y pulsa Revisar producción.', 'Comprueba vaca por vaca y el total antes de confirmar.', 'Confirma una sola vez y espera el mensaje verde de aceptación del servidor.'], caution: 'No prepares una entrega mientras el lote figure pendiente o guardado solo en este teléfono.' },
    { title: 'Preparar una entrega', summary: 'Asigna parte de un lote confirmado a una entrega.', to: '/entregas/preparar', steps: ['Selecciona el lote confirmado, la presentación y la cantidad de bolsas.', 'Elige destino, conductor y receptor autorizados. Conductor y receptor deben ser personas distintas.', 'Verifica que la cantidad física coincida con lo escrito.', 'Guarda el borrador; después abre Revisar y enviar para comprobar y enviar la solicitud.'], caution: 'Guardar el borrador no avisa al transportista. Debes revisar y enviar la solicitud.' },
    { title: 'Vacas', summary: 'Consulta las vacas activas autorizadas para tu centro.', to: '/vacas', steps: ['Busca la vaca por su código antes de registrar.', 'Si falta una vaca o pertenece a otro centro, solicita el cambio al administrador.'] },
    { title: 'Historial', summary: 'Consulta producciones, borradores y correcciones anteriores.', to: '/historial', steps: ['Abre una producción para revisar sus litros y versiones.', 'Descarta únicamente borradores que no deban enviarse.', 'Usa la corrección o anulación solo cuando exista un error real y explica el motivo.'] },
  ],
  TRANSPORTE: [
    { title: 'Recoger una entrega', summary: 'Confirma que la leche salió físicamente del centro.', to: '/recogidas', steps: ['Pulsa Actualizar solicitudes si tienes conexión.', 'Comprueba código, origen, destino y cantidad de bolsas.', 'Compara la cantidad mostrada con la leche que recibes físicamente.', 'Pulsa Confirmar recogida solo después de recibirla.', 'Espera la confirmación del servidor; entonces Recepción podrá ver la entrega.'], caution: 'Una nota provisional no confirma la recogida y una cantidad incorrecta no debe confirmarse.' },
    { title: 'Diario', summary: 'Consulta las cantidades recogidas y recibidas por fecha.', to: '/diario', steps: ['Selecciona el mes.', 'Elige un día para consultar sus movimientos.', 'Usa esta pantalla solo para consulta; no confirma operaciones.'] },
    { title: 'Pendientes', summary: 'Muestra solicitudes de corrección que requieren atención.', to: '/pendientes', steps: ['Lee el motivo y compara los datos originales con la propuesta.', 'Aprueba únicamente si verificaste el cambio; rechaza si no corresponde.', 'No confundas aprobar una corrección con confirmar una recogida.'] },
  ],
  RECEPCION: [
    { title: 'Recibir una entrega', summary: 'Confirma la llegada física de la leche al punto de venta.', to: '/recibir', steps: ['Pulsa Actualizar recepciones si tienes conexión.', 'Comprueba código, origen, conductor y cantidad.', 'Cuenta o verifica físicamente las bolsas recibidas.', 'Pulsa Confirmar recepción física solo después de tener la leche.', 'Espera el mensaje de aceptación del servidor.'], caution: 'Si existe una corrección pendiente, resuélvela antes. Leer un aviso no equivale a recibir la leche.' },
    { title: 'Recepciones', summary: 'Consulta el historial de entregas que ya fueron recibidas.', to: '/recepciones', steps: ['Busca la fecha que necesitas revisar.', 'Comprueba origen, destino y litros recibidos.', 'Utiliza el historial para consulta, no para volver a confirmar.'] },
    { title: 'Pendientes', summary: 'Muestra correcciones que debes revisar.', to: '/pendientes', steps: ['Lee el motivo y revisa la cantidad propuesta.', 'Aprueba solo si coincide con lo comprobado físicamente.', 'Después vuelve a Recepciones pendientes para completar la recepción.'] },
  ],
  ADMIN: [
    { title: 'Resumen y administración', summary: 'Presenta indicadores y accesos a las tareas administrativas.', to: '/administracion', steps: ['Revisa los indicadores antes de modificar datos.', 'Entra a Cuentas, Catálogos o Reasignar receptor según la tarea.', 'No confirmes producción, recogida o recepción en nombre de otro usuario.'] },
    { title: 'Trazabilidad', summary: 'Muestra el origen y el recorrido real de cada lote.', to: '/administracion/lotes', steps: ['Busca por código de lote.', 'Abre el lote y revisa cada entrega por separado.', 'Comprueba responsables, horas y estados.', 'Los borradores no enviados aparecen informados, pero no se dibujan como recorridos.'] },
    { title: 'Cuentas', summary: 'Crea usuarios y asigna sus funciones y ubicaciones.', to: '/administracion/usuarios', steps: ['Crea una cuenta personal; nunca compartas usuarios.', 'Entrega la contraseña temporal fuera de SITRAP.', 'Asigna el rol y la ubicación correctos.', 'Para retirar acceso, finaliza la asignación o desactiva la cuenta sin borrar su historial.'], caution: 'No desactives una cuenta hasta verificar que no sea necesaria para el trabajo en curso.' },
    { title: 'Catálogos', summary: 'Administra centros, productos, presentaciones y datos maestros.', to: '/administracion/catalogos', steps: ['Selecciona el catálogo correcto antes de escribir.', 'Usa códigos únicos y nombres fáciles de reconocer.', 'Comprueba relaciones de centro, producto y presentación.', 'Desactiva registros antiguos; no los reemplaces borrando su historia.'] },
    { title: 'Reasignar receptor', summary: 'Cambia el receptor permitido de una entrega cuando corresponde.', to: '/administracion/reasignar', steps: ['Identifica la entrega correcta.', 'Selecciona una cuenta autorizada para el destino.', 'Verifica el cambio antes de guardarlo y comunica la reasignación a las personas involucradas.'] },
  ],
}

export function HelpPage() {
  const { assignment } = useWorkspace()
  if (!assignment) return <Notice tone="warning">No tienes una función activa para mostrar su guía.</Notice>
  return <section className="stack help-page">
    <div className="help-hero"><span className="help-hero__icon" aria-hidden="true">?</span><div><p className="trace-eyebrow">Guía de uso</p><h1>Cómo usar SITRAP</h1><p>Instrucciones para tu función de <strong>{roleLabels[assignment.role]}</strong>. Puedes volver a esta página cuando lo necesites.</p></div></div>
    <Notice><strong>Antes de registrar:</strong> confirma que ves tu nombre, función y ubicación correctos. Lee todos los datos antes de pulsar Confirmar.</Notice>
    <div className="help-guides">
      {guides[assignment.role].map((guide, index) => <article className="card stack help-guide" key={guide.title}>
        <div className="help-guide__heading"><span aria-hidden="true">{index + 1}</span><div><h2>{guide.title}</h2><p>{guide.summary}</p></div></div>
        <ol>{guide.steps.map(step => <li key={step}>{step}</li>)}</ol>
        {guide.caution && <Notice tone="warning"><strong>Importante:</strong> {guide.caution}</Notice>}
        {guide.to && <Link className="button secondary help-guide__link" to={guide.to}>Ir a {guide.title.toLowerCase()}</Link>}
      </article>)}
    </div>
    <section className="card stack"><h2>¿Cómo sé si quedó registrado?</h2><ul><li><strong>Mensaje verde:</strong> el servidor aceptó la operación.</li><li><strong>Mensaje amarillo:</strong> está guardada solo en el teléfono o requiere revisión.</li><li><strong>Mensaje rojo:</strong> no continúes; corrige el dato o solicita ayuda.</li></ul><p>Si trabajaste sin conexión, abre el estado de sincronización desde <strong>Cuenta y ajustes</strong> antes de cerrar sesión.</p></section>
  </section>
}
