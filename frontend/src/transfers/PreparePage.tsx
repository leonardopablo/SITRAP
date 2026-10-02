import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { createCommand } from '../api/commands'
import { enqueue, getDevice, saveCopy } from '../offline/db'
import { useConnection } from '../offline/SyncPanel'
import { Button, Field, Notice } from '../components/ui'
import { defaults, validateBags } from './prepare'
import type { AssignmentOptions, Lot, Presentation } from './types'

export function PreparePage() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const [lotId, setLotId] = useState('')
  const [presentationId, setPresentationId] = useState('')
  const [bags, setBags] = useState('')
  const [destinationId, setDestinationId] = useState('')
  const [driverId, setDriverId] = useState('')
  const [receiverId, setReceiverId] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [saving, setSaving] = useState(false)
  const key = [account?.id, assignment?.id]
  const lots = useQuery({ queryKey: ['lots', ...key], queryFn: () => api.request<Page<Lot>>('/lots'), enabled: !!account && !!assignment && online })
  const presentations = useQuery({ queryKey: ['presentations', ...key], queryFn: () => api.request<Page<Presentation>>('/presentations'), enabled: !!account && !!assignment && online })
  const options = useQuery({ queryKey: ['assignment-options', ...key], queryFn: () => api.request<AssignmentOptions>(`/assignment-options?origin_id=${encodeURIComponent(assignment!.location_id ?? '')}`), enabled: !!account && !!assignment?.location_id && online })
  useEffect(() => { if (lots.data?.results.length === 1) setLotId(lots.data.results[0].id) }, [lots.data])
  useEffect(() => { if (presentations.data?.results.length === 1) setPresentationId(presentations.data.results[0].id) }, [presentations.data])
  useEffect(() => { if (options.data) { const chosen = defaults(options.data); setDestinationId(chosen.destination_id); setDriverId(chosen.driver_id); setReceiverId(chosen.receiver_id) } }, [options.data])
  const lot = lots.data?.results.find(item => item.id === lotId)
  const presentation = presentations.data?.results.find(item => item.id === presentationId)
  async function save() {
    if (!account || !assignment?.location_id || !lot || !presentation || !options.data || saving) return
    setError(''); setSaved('')
    try {
      const amount = validateBags(bags, lot, presentation)
      if (!options.data.destinations.some(item => item.id === destinationId) || !options.data.drivers.some(item => item.id === driverId) || !options.data.receivers.some(item => item.id === receiverId)) throw new Error('Elige destino, conductor y receptor autorizados.')
      if (driverId === receiverId) throw new Error('Conductor y receptor deben ser cuentas distintas.')
      setSaving(true)
      const device = await getDevice(account.id)
      const transferId = crypto.randomUUID(); const versionId = crypto.randomUUID()
      const command = createCommand({ type: 'TRANSFER_CREATE', entity_id: transferId, device_id: device.device_id, payload: { version_id: versionId, lot_id: lot.id, presentation_id: presentation.id, units_presentation: amount, origin_id: assignment.location_id, destination_id: destinationId, driver_id: driverId, receiver_id: receiverId } })
      await enqueue(account.id, command)
      await saveCopy(account.id, 'transfer-draft', transferId, { version_id: versionId, lot_id: lot.id, units_presentation: amount, destination_id: destinationId, driver_id: driverId, receiver_id: receiverId, event_id: command.event_id })
      setSaved(command.event_id)
    } catch (cause) { setError((cause as Error).message) }
    finally { setSaving(false) }
  }
  return <section className="stack form"><h1>Preparar entrega</h1>
    {apiMode === 'mock' && <Notice tone="warning">Lote y personas de DEMOSTRACIÓN. Solo se guardará un borrador en este teléfono; no hay solicitud ni aviso para transporte.</Notice>}
    <p>Elige un lote confirmado y revisa la cantidad disponible. “No vinculado” no es inventario físico.</p>
    {lots.isPending || options.isPending || presentations.isPending ? <Notice>Cargando opciones…</Notice> : null}
    {lots.isError || options.isError || presentations.isError ? <Notice tone="error">No se pudieron obtener lotes, presentaciones u opciones. Reintenta con conexión.</Notice> : null}
    <div className="field"><label htmlFor="transfer-lot">Lote de origen</label><select id="transfer-lot" value={lotId} onChange={event => setLotId(event.target.value)}><option value="">Selecciona lote</option>{lots.data?.results.filter(item => item.confirmed && item.center_id === assignment?.location_id).map(item => <option key={item.id} value={item.id}>{item.code} · {item.unlinked_litres} L no vinculados</option>)}</select></div>
    <div className="field"><label htmlFor="transfer-presentation">Presentación</label><select id="transfer-presentation" value={presentationId} onChange={event => setPresentationId(event.target.value)}><option value="">Selecciona presentación</option>{presentations.data?.results.filter(item => item.active && item.content_base === '1.000' && !item.admits_fraction && item.product_id === lot?.product_id).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
    <Field label="Bolsas de 1 L" inputMode="numeric" value={bags} onChange={event => setBags(event.target.value)} help="Una bolsa equivale a 1 L en este piloto." />
    <p className="quantity">{/^\d+$/.test(bags) ? bags : '0'} bolsas · {/^\d+$/.test(bags) ? bags : '0'} L</p>
    {([['Destino', destinationId, setDestinationId, options.data?.destinations], ['Conductor', driverId, setDriverId, options.data?.drivers], ['Receptor', receiverId, setReceiverId, options.data?.receivers]] as const).map(([label, value, setter, choices]) => <div className="field" key={label}><label htmlFor={`option-${label}`}>{label}</label><select id={`option-${label}`} value={value} onChange={event => setter(event.target.value)}><option value="">Selecciona {label.toLowerCase()}</option>{choices?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>)}
    {error && <Notice tone="error">{error}</Notice>}
    <Button busy={saving} disabled={!online || !lot || !presentation || !options.data || !!saved} onClick={() => void save()}>Guardar borrador de entrega</Button>
    {saved && <Notice tone="warning">Borrador guardado solo en este teléfono (evento {saved}). Aún no se envió a transporte. F17 añadirá el envío.</Notice>}
  </section>
}
