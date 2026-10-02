import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'

type CatalogName = 'locations' | 'products' | 'center-products' | 'presentations' | 'turns' | 'species'
interface Row { id: string; code?: string; name?: string; active?: boolean; type?: string; center_id?: string; product_id?: string; enabled?: boolean; content_base?: string; admits_fraction?: boolean }
const labels: Record<CatalogName, string> = { locations: 'Centros y puntos de venta', products: 'Productos', 'center-products': 'Productos habilitados por centro', presentations: 'Presentaciones', turns: 'Turnos', species: 'Especies' }
export function CatalogPage() {
  const { account } = useAuth()
  const online = useConnection()
  const cache = useQueryClient()
  const [catalog, setCatalog] = useState<CatalogName>('locations')
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [center, setCenter] = useState('')
  const [product, setProduct] = useState('')
  const [locationType, setLocationType] = useState('CENTRO')
  const [content, setContent] = useState('1.000')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const key = (name: CatalogName) => ['catalog', account?.id, name]
  const items = useQuery({ queryKey: key(catalog), queryFn: () => api.request<Page<Row>>(`/${catalog}`), enabled: !!account && online })
  const centers = useQuery({ queryKey: key('locations'), queryFn: () => api.request<Page<Row>>('/locations'), enabled: !!account && online })
  const products = useQuery({ queryKey: key('products'), queryFn: () => api.request<Page<Row>>('/products'), enabled: !!account && online })
  async function run(action: () => Promise<unknown>, success: string) { setBusy(true); setMessage(''); try { await action(); await cache.invalidateQueries({ queryKey: ['catalog', account?.id] }); setMessage(apiMode === 'mock' ? `${success} (solo simulación)` : success) } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) } }
  function create() {
    const body = catalog === 'center-products' ? { center_id: center, product_id: product, enabled: true } : catalog === 'presentations' ? { name, product_id: product, content_base: content, admits_fraction: false, active: true } : { code, name, active: true, ...(catalog === 'locations' ? { type: locationType } : {}), ...(catalog === 'products' ? { unit: 'L' } : {}) }
    void run(async () => { await api.post(`/${catalog}`, body); setCode(''); setName('') }, 'Catálogo guardado')
  }
  return <section className="stack"><h1>Catálogos</h1>
    {apiMode === 'mock' && <Notice tone="warning">Catálogos de demostración. Los cambios no están conectados al servidor.</Notice>}
    <p>Habilitar un producto no crea stock, venta ni proceso operativo de otras especies. Los catálogos usados se desactivan y conservan historia.</p>
    <div className="field form"><label htmlFor="catalog-type">Catálogo a editar</label><select id="catalog-type" value={catalog} onChange={event => setCatalog(event.target.value as CatalogName)}>{(Object.keys(labels) as CatalogName[]).map(item => <option value={item} key={item}>{labels[item]}</option>)}</select></div>
    <section className="card stack form"><h2>Agregar {labels[catalog].toLowerCase()}</h2>
      {!['center-products', 'presentations'].includes(catalog) && <><div className="field"><label htmlFor="catalog-code">Código</label><input id="catalog-code" value={code} onChange={event => setCode(event.target.value)} /></div><div className="field"><label htmlFor="catalog-name">Nombre</label><input id="catalog-name" value={name} onChange={event => setName(event.target.value)} /></div></>}
      {catalog === 'presentations' && <div className="field"><label htmlFor="catalog-presentation-name">Nombre</label><input id="catalog-presentation-name" value={name} onChange={event => setName(event.target.value)} /></div>}
      {catalog === 'locations' && <div className="field"><label htmlFor="location-kind">Tipo</label><select id="location-kind" value={locationType} onChange={event => setLocationType(event.target.value)}><option value="CENTRO">Centro</option><option value="PUNTO_VENTA">Punto de venta</option></select></div>}
      {catalog === 'center-products' && <div className="field"><label htmlFor="catalog-center">Centro</label><select id="catalog-center" value={center} onChange={event => setCenter(event.target.value)}><option value="">Selecciona</option>{centers.data?.results.filter(item => item.type === 'CENTRO').map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>}
      {['center-products', 'presentations'].includes(catalog) && <div className="field"><label htmlFor="catalog-product">Producto</label><select id="catalog-product" value={product} onChange={event => setProduct(event.target.value)}><option value="">Selecciona</option>{products.data?.results.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>}
      {catalog === 'presentations' && <div className="field"><label htmlFor="catalog-content">Contenido base (unidad del producto)</label><input id="catalog-content" inputMode="decimal" value={content} onChange={event => setContent(event.target.value)} /></div>}
      <Button busy={busy} disabled={!online || (catalog === 'center-products' ? !center || !product : !name.trim() || (catalog === 'presentations' ? !product || Number(content) <= 0 : !code.trim()))} onClick={create}>Guardar catálogo</Button>
    </section>
    {message && <Notice>{message}</Notice>}{items.isPending && <Notice>Cargando catálogo…</Notice>}{items.isError && <Notice tone="error">No se pudo consultar el catálogo.</Notice>}
    {items.data?.results.map(item => <article key={item.id} className="card"><h3>{item.name ?? `${item.center_id} · ${item.product_id}`}</h3><p>{item.code ?? item.content_base ?? ''} · {item.enabled === false || item.active === false ? 'Desactivado' : 'Activo'}</p>
      <Button variant="secondary" disabled={!online || busy || item.active === false || item.enabled === false} onClick={() => void run(() => api.patch(`/${catalog}/${item.id}`, catalog === 'center-products' ? { enabled: false } : { active: false }), 'Desactivado sin borrar historial')}>Desactivar</Button>
    </article>)}
    <Link to="/administracion/usuarios">Gestionar cuentas y ámbitos</Link>
  </section>
}
