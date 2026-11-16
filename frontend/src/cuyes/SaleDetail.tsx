import { useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Acknowledgement } from '../api/types'
import { Button, Notice } from '../components/ui'
import { db, getDevice } from '../offline/db'
import { SalePreparationForm } from './SalePreparationForm'
import type { Candidate, Sale, SalesOptions, SaleType } from './salesTypes'

const stamp = (value: string) => new Date(value).toLocaleString('es-PE', { timeZone: 'America/Lima' })
export function SaleDetail({ accountId, order, role, options, candidates, shedIds, perform, refresh }: {
  accountId: string; order: Sale; role: string; options?: SalesOptions; candidates: Candidate[]; shedIds: string[];
  perform: (type: SaleType, payload: Record<string, unknown>) => Promise<boolean>; refresh: () => void
}) {
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const [pinShown, setPinShown] = useState('')
  const [pinInput, setPinInput] = useState('')
  const [driver, setDriver] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [evidenceId, setEvidenceId] = useState('')
  const [method, setMethod] = useState('Transferencia')
  const [reference, setReference] = useState('')
  const [physical, setPhysical] = useState('')
  const [delivered, setDelivered] = useState(false)
  const [weightLine, setWeightLine] = useState('')
  const [weight, setWeight] = useState('')
  const [treatment, setTreatment] = useState('ABSORBIDO')
  const [cancelTreatment, setCancelTreatment] = useState('')
  const [proposalLine, setProposalLine] = useState('')
  const [proposalUnits, setProposalUnits] = useState(1)
  const [busy, setBusy] = useState(false)
  const attempt = useRef<{ id: string; version: number } | null>(null)
  const has = (action: string) => order.actions.includes(action)
  async function privateAction(action: () => Promise<unknown>) {
    setBusy(true); setMessage('')
    try { await action(); refresh() } catch (e) { setMessage((e as Error).message) } finally { setBusy(false) }
  }
  async function upload() {
    if (!file) throw new Error('Selecciona un comprobante privado.')
    const id = evidenceId || crypto.randomUUID(); setEvidenceId(id)
    const data = new FormData(); data.set('id', id); data.set('file', file)
    const result = await api.request<{ id: string }>('/cuyes/sales/vouchers', { method: 'POST', body: data })
    setEvidenceId(result.id); setMessage('Comprobante privado cargado; todavía no valida el pago.')
  }
  const ownSelectedSheds = [...new Set(order.preparation?.items.filter(i => shedIds.includes(i.shed_id ?? '')).map(i => i.shed_id!) ?? [])]
  const conformity = { preparation_id: order.preparation?.id, round: order.preparation?.round, reason }
  return <section className="stack"><section className="card stack"><h2>Orden {order.code}</h2><p>{order.center} · {order.mode === 'DIRECTO' ? 'Recojo directo' : `Punto de venta: ${order.point?.name}`}</p>
    <ol className="sale-stages" aria-label="Etapas de venta">{['Solicitado', 'Confirmado y pagado', 'Preparación / ruta', 'Entregado'].map((s, i) => <li key={s} aria-current={order.stage === i + 1 ? 'step' : undefined}>{i + 1}. {s}</li>)}</ol>
    <strong>Estado: {order.display_state}</strong><p>Cliente: {order.client.name}{order.client.contact && ` · contacto: ${order.client.contact}`}</p>
    {order.reason && <p>Último motivo registrado: {order.reason}</p>}{order.manager && <p>Responsable administrativo: {order.manager.name}</p>}
    {order.shortage && <Notice tone="error">Faltan existencias comprometidas. No se despachará hasta revisión administrativa.</Notice>}{order.financial_hold && <Notice tone="warning">Cambió el peso o importe después del pago. Despacho bloqueado hasta revisión.</Notice>}
    {order.total && <p>Total acordado: {order.currency} {order.total} · Importe autorizado: {order.approved_total ?? 'pendiente'}</p>}
    {order.lines.map((line, index) => <article className="card" key={line.id}><h3>Ítem {index + 1} · {line.kind}</h3><p>{line.units} {line.kind === 'MODULO' ? 'módulos' : 'animales'} · Retiro físico: {line.animal_count} animales</p><p>Composición por unidad: {line.recipe.map(c => `${c.quantity} ${c.category}/${c.quality}`).join(' + ')}</p>{line.weight_kg && <p>Peso de cobro confirmado: {line.weight_kg} KG · {line.weight_basis}</p>}{line.total && <p>Precio: {line.unit_price}/{line.billing_unit} · Total: {line.total}</p>}</article>)}
    {order.reservation && <Notice>Reserva: {order.reservation.state} · Vencimiento impago: {stamp(order.reservation.expires_at)}{order.reservation.state === 'PAGADA' && ' · Pagada: no se libera automáticamente.'}{order.reservation.consumed_at && ` · Consumida al salir: ${stamp(order.reservation.consumed_at)}`}</Notice>}
    {order.payment && <p>Pago original validado: {order.payment.currency} {order.payment.amount} · {order.payment.reference} · <a href={`/api/v1/cuyes/sales/vouchers/${order.payment.evidence_id}`}>Descargar comprobante privado</a></p>}
    {order.financial_reviews?.map(r => <p key={r.id}>Resolución: {r.treatment} · diferencia {r.difference} · {r.reference} · {r.reason}</p>)}
    {order.reservation_history && order.reservation_history.length > 1 && <details><summary>Historial de reservas</summary>{order.reservation_history.map(r => <p key={r.id}>{r.state} · creada {stamp(r.created_at)} · vence {stamp(r.expires_at)}{r.released_at && ` · liberada ${stamp(r.released_at)}`}{r.consumed_at && ` · consumida ${stamp(r.consumed_at)}`}</p>)}</details>}
    <p>Última actualización: {stamp(order.updated_at)}. Solo saldo confirmado, sin intenciones offline.</p>
  </section>
  <section className="card stack form"><h3>Acciones autorizadas</h3><label>Motivo de la acción<input required value={reason} maxLength={500} onChange={e => setReason(e.target.value)} /></label>
    {has('SALE_CONFIRM') && <Button disabled={!reason} onClick={() => void perform('SALE_CONFIRM', { reason })}>Confirmar disponibilidad y reservar todo</Button>}
    {has('SALE_REJECT') && <Button disabled={!reason} variant="danger" onClick={() => void perform('SALE_REJECT', { reason })}>Rechazar con motivo</Button>}
    {has('SALE_PROPOSE') && <details><summary>Proponer ajuste de disponibilidad (sin cambiar precios)</summary><div className="stack"><label>Ítem a ajustar<select aria-label="Ítem a ajustar" value={proposalLine} onChange={e => setProposalLine(e.target.value)}><option value="">Selecciona</option>{order.lines.map((l, i) => <option key={l.id} value={l.id}>Ítem {i + 1} · {l.kind}</option>)}</select></label><label>Cantidad propuesta (módulos o animales)<input type="number" min="1" step="1" value={proposalUnits} onChange={e => setProposalUnits(Number(e.target.value))} /></label><Button disabled={!reason || !proposalLine} onClick={() => void perform('SALE_PROPOSE', { reason, items: [{ line_id: proposalLine, units: proposalUnits }] })}>Enviar propuesta a ADMIN</Button></div></details>}
    {has('SALE_PROPOSAL_REVIEW') && order.proposals?.filter(p => p.state === 'PENDIENTE').map(p => <article key={p.id}><p>{p.reason} · Propuesta: {JSON.stringify(p.items)}</p><Button disabled={!reason} onClick={() => void perform('SALE_PROPOSAL_REVIEW', { reason, proposal_id: p.id, approve: true })}>Aceptar ajuste; solicitar nueva confirmación</Button><Button disabled={!reason} variant="secondary" onClick={() => void perform('SALE_PROPOSAL_REVIEW', { reason, proposal_id: p.id, approve: false })}>Rechazar ajuste</Button></article>)}
    {(has('SALE_PAY') || has('SALE_FINANCE')) && <div className="stack"><label>Comprobante privado (PDF/JPEG/PNG, hasta 5 MiB)<input type="file" accept="application/pdf,image/png,image/jpeg" onChange={e => { setFile(e.target.files?.[0] ?? null); setEvidenceId('') }} /></label><Button busy={busy} disabled={!file} variant="secondary" onClick={() => void privateAction(upload)}>Cargar comprobante privado</Button><label>Medio de pago<input value={method} onChange={e => setMethod(e.target.value)} /></label><label>Referencia de pago o ajuste<input value={reference} onChange={e => setReference(e.target.value)} maxLength={150} /></label>
      {has('SALE_PAY') && <><p>Verifica el comprobante y el peso antes de validar. Se registrará exactamente {order.currency} {order.total}.</p><Button disabled={!reason || !evidenceId || !reference || !method} onClick={() => void perform('SALE_PAY', { reason, amount: order.total, currency: order.currency, method, reference, evidence_id: evidenceId })}>Validar pago manual por importe acordado</Button></>}
      {has('SALE_FINANCE') && <><label>Tratamiento de la diferencia<select aria-label="Tratamiento de la diferencia" value={treatment} onChange={e => setTreatment(e.target.value)}><option>ABSORBIDO</option><option>COBRO_ADICIONAL</option><option>DEVOLUCION</option></select></label><Button disabled={!reason || !reference || (treatment !== 'ABSORBIDO' && !evidenceId)} onClick={() => void perform('SALE_FINANCE', { reason, treatment, reference, ...(evidenceId ? { evidence_id: evidenceId } : {}) })}>Resolver diferencia económica con motivo</Button></>}
    </div>}
    {has('SALE_WEIGH') && <div className="stack"><label>Línea por peso<select aria-label="Línea por peso" value={weightLine} onChange={e => setWeightLine(e.target.value)}><option value="">Selecciona</option>{order.lines.filter(l => l.kind === 'PESO').map(l => <option key={l.id} value={l.id}>{l.animal_count} animales · {l.weight_kg} KG</option>)}</select></label><label>Peso definitivo confirmado (KG, 3 decimales)<input type="number" min=".001" step=".001" value={weight} onChange={e => setWeight(e.target.value)} /></label><Button disabled={!reason || !weightLine || !weight} onClick={() => void perform('SALE_WEIGH', { reason, line_id: weightLine, weight_kg: weight })}>Registrar peso e importe revisados</Button></div>}
    {has('PIN_GENERATE') && <div className="stack"><Button busy={busy} disabled={!reason} onClick={() => void privateAction(async () => { setPinShown(''); const result = await api.post<{ pin: string }>(`/cuyes/sales/orders/${order.id}/pin`, { reason, expected_version: order.version }); setPinShown(result.pin) })}>Generar o regenerar PIN (invalida el anterior)</Button>{pinShown && <Notice>PIN de una sola entrega: <strong>{pinShown}</strong>. Entrégalo al cliente fuera de la aplicación. <Button variant="secondary" onClick={() => setPinShown('')}>Ocultar PIN</Button></Notice>}</div>}
    {has('SALE_DRIVER') && <div className="stack"><label>Conductor autorizado<select aria-label="Conductor autorizado" value={driver} onChange={e => setDriver(e.target.value)}><option value="">Selecciona</option>{options?.drivers.filter(d => d.center_ids.includes(order.center_id)).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label><Button disabled={!reason || !driver} onClick={() => void perform('SALE_DRIVER', { reason, driver_id: driver })}>Asignar conductor y activar viaje</Button></div>}
    {has('SALE_ORIGIN') && order.preparation && <Button disabled={!reason || !ownSelectedSheds.length} onClick={() => void perform('SALE_ORIGIN', { ...conformity, shed_ids: ownSelectedSheds })}>Dar conformidad de mis galpones sobre este detalle</Button>}
    {has('SALE_PICKUP') && order.preparation && <Button disabled={!reason} onClick={() => void perform('SALE_PICKUP', { ...conformity, shed_ids: [] })}>Estoy conforme con las cantidades a recoger</Button>}
    {has('SALE_DEPART') && <Button disabled={!reason} onClick={() => void perform('SALE_DEPART', { reason })}>Confirmar salida física (descuenta una sola vez)</Button>}
    {(has('PIN_DELIVER') || has('SALE_ARRIVE') || has('SALE_COLLECT')) && <><label>Quién realiza físicamente la entrega<input value={physical} onChange={e => setPhysical(e.target.value)} maxLength={150} /></label><label>Referencia de conformidad del cliente / entrega<input value={reference} onChange={e => setReference(e.target.value)} maxLength={150} /></label></>}
    {has('PIN_DELIVER') && <div className="stack"><label>PIN presentado por el cliente<input value={pinInput} onChange={e => setPinInput(e.target.value)} inputMode="numeric" autoComplete="off" type="password" maxLength={8} /></label><Button busy={busy} disabled={!reason || !physical || !reference || !/^\d{8}$/.test(pinInput)} onClick={() => void privateAction(async () => {
      const device = await getDevice(accountId)
      if (!device.registered) { await api.post('/devices', { id: device.device_id, name: 'SITRAP PWA' }); await db.devices.update(accountId, { registered: true }) }
      attempt.current ??= { id: crypto.randomUUID(), version: order.version }
      try {
        const ack = await api.post<Acknowledgement>(`/cuyes/sales/orders/${order.id}/deliver-direct`, { event_id: attempt.current.id, device_id: device.device_id, expected_version: attempt.current.version, pin: pinInput, reason, physical_responsible: physical, reference })
        if (ack.status !== 'APLICADA') throw new Error(ack.error?.message ?? 'No se confirmó la salida.')
        setPinInput(''); attempt.current = null; setMessage('Salida y entrega al cliente confirmadas.')
      } catch (error) { if (error instanceof ApiError && error.status > 0 && error.status < 500) attempt.current = null; throw error }
    })}>Validar PIN, retirar inventario y entregar al cliente</Button></div>}
    {has('SALE_ARRIVE') && <><label><input type="checkbox" checked={delivered} onChange={e => setDelivered(e.target.checked)} /> Entrego ahora directamente al cliente (no solo dejo el pedido)</label><Button disabled={!reason || !physical || !reference} onClick={() => void perform('SALE_ARRIVE', { reason, physical_responsible: physical, reference, delivered_to_client: delivered })}>Confirmar llegada al punto de venta</Button></>}
    {has('SALE_COLLECT') && <Button disabled={!reason || !physical || !reference} onClick={() => void perform('SALE_COLLECT', { reason, physical_responsible: physical, reference })}>Registrar retiro posterior del cliente</Button>}
    {has('SALE_RESOLVE_STOCK') && <Button disabled={!reason} onClick={() => void perform('SALE_RESOLVE_STOCK', { reason })}>Revisar faltante y habilitar nuevas conformidades</Button>}
    {has('SALE_CANCEL') && <details><summary>Cancelar antes del despacho</summary><p>No devuelve animales al inventario ni ejecuta reembolsos. Debe dejar explícita la resolución del pago.</p><label>Tratamiento del pago (obligatorio si ya está pagada)<textarea value={cancelTreatment} onChange={e => setCancelTreatment(e.target.value)} maxLength={500} /></label><Button disabled={!reason || (!!order.payment && !cancelTreatment)} variant="danger" onClick={() => void perform('SALE_CANCEL', { reason, ...(cancelTreatment ? { payment_treatment: cancelTreatment } : {}) })}>Cancelar y liberar con resolución auditada</Button></details>}
    {message && <Notice>{message}</Notice>}
  </section>
  {role === 'GALPONERO' && has('SALE_SELECT') && <SalePreparationForm key={`${order.id}:${order.preparation?.id ?? 'new'}`} order={order} candidates={candidates} shedIds={shedIds} perform={perform} />}
  {order.preparation && <section className="card"><h3>Detalle vigente y conformidades</h3>{order.preparation.items.map((i, n) => <p key={n}>{i.pen} · {i.category}/{i.quality}: {i.quantity}</p>)}{order.preparation.conformities.map((c, i) => <p key={i}>{c.stage} · galpón {c.shed_id ?? 'conductor asignado'} · {stamp(c.registered_at)}</p>)}</section>}
  {order.dispatch && <section className="card"><h3>Trazabilidad del retiro efectivo</h3><p>Salida {stamp(order.dispatch.departed_at)} · Movimiento {order.dispatch.movement_id}</p>{order.dispatch.details.map((d, i) => <p key={i}>{String(d.snapshot.center)} / {String(d.snapshot.shed)} / {String(d.snapshot.pen)} · lote {String(d.snapshot.lot_id)} · {d.category}/{d.quality}: {d.quantity} · Edad al salir: {d.snapshot.age_days_min == null ? 'edad desconocida' : `${d.snapshot.age_days_min}–${d.snapshot.age_days_max} días`}</p>)}</section>}
  <section className="card"><h3>Hechos de entrega</h3>{order.deliveries.map(d => <p key={d.stage}>{d.stage} · {stamp(d.registered_at)} · Realizó: {d.physical_responsible} · Registró: {d.registered_by_id} · Referencia: {d.reference}</p>)}</section>
  </section>
}
