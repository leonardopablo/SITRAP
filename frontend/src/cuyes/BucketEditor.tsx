import { Button } from '../components/ui'
import type { Bucket, Category, Destination, Occupation } from './types'

export const blankBucket = (): Bucket => ({ category: 'MACHO', quality: 'SIN_CLASIFICAR', quantity: 0 })
export function BucketEditor({ value, onChange, occupations, destinations, weaning = false, count = false, categories = ['MACHO', 'HEMBRA', 'LACTANTE'] }: {
  value: Bucket[]; onChange: (items: Bucket[]) => void; occupations?: Occupation[]; destinations?: Destination[]; weaning?: boolean; count?: boolean; categories?: Category[]
}) {
  const update = (index: number, patch: Partial<Bucket>) => onChange(value.map((item, i) => i === index ? { ...item, ...patch } : item))
  return <div className="stack">{value.map((item, index) => <fieldset className="card stack" key={index}><legend>Línea {index + 1}</legend>
    {occupations && <label>Lote / ocupación<select aria-label="Lote / ocupación" required value={item.occupation_id ?? ''} onChange={e => update(index, { occupation_id: e.target.value })}><option value="">Selecciona el lote</option>{occupations.map(o => <option key={o.id} value={o.id}>{o.lot.provenance} · {o.lot.id.slice(0, 8)} · {o.started_on}</option>)}</select></label>}
    {destinations && <label>Poza de destino<select aria-label="Poza de destino" required value={item.pen_id ?? ''} onChange={e => update(index, { pen_id: e.target.value })}><option value="">Selecciona destino</option>{destinations.filter(d => !weaning || d.purpose === (item.category === 'MACHO' ? 'RECRIA_MACHOS' : 'RECRIA_HEMBRAS')).map(d => <option key={d.id} value={d.id}>{d.code}</option>)}</select></label>}
    <label>Categoría<select aria-label="Categoría" value={item.category} onChange={e => update(index, { category: e.target.value as Bucket['category'], pen_id: undefined })}>{(weaning ? ['MACHO', 'HEMBRA'] : categories).map(c => <option key={c}>{c}</option>)}</select></label>
    <label>Calidad<select aria-label="Calidad" value={item.quality} onChange={e => update(index, { quality: e.target.value as Bucket['quality'] })}>{(weaning ? ['A', 'B'] : ['SIN_CLASIFICAR', 'A', 'B', 'C']).map(q => <option key={q}>{q}</option>)}</select></label>
    <label>{count ? 'Cantidad observada' : 'Cantidad'}<input required type="number" min={count ? 0 : 1} step="1" value={item.quantity} onChange={e => update(index, { quantity: Number(e.target.value) })} /></label>
    {value.length > 1 && <Button type="button" variant="secondary" onClick={() => onChange(value.filter((_, i) => i !== index))}>Quitar línea</Button>}
  </fieldset>)}<Button type="button" variant="secondary" onClick={() => onChange([...value, { ...blankBucket(), category: categories[0], ...(weaning ? { quality: 'B' as const } : {}) }])}>Añadir línea</Button></div>
}
