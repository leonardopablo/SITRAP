import 'fake-indexeddb/auto'
import { api } from '../api/client'
import { applyChanges, prepareAccount } from './prepare'
import { getDevice, saveCopy, SitrapDB } from './db'

it('prepara una sola cuenta sin borrar copias ni eventos de otra', async () => {
  const store = new SitrapDB(`prepare-${crypto.randomUUID()}`)
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  await saveCopy('other', 'transfer', 't1', { version_id: 'v1' }, store)
  await saveCopy('one', 'transfer', 'obsolete', { version_id: 'old' }, store)
  const device = await getDevice('one', store)
  await prepareAccount('one', store)
  expect(await store.copies.where('account_id').equals('one').count()).toBe(0)
  expect(await store.copies.where('account_id').equals('other').count()).toBe(1)
  expect((await store.devices.get('one'))?.device_id).toBe(device.device_id)
  expect((await store.devices.get('one'))?.registered).toBe(true)
  expect(await applyChanges('one', store)).toBe(0)
  store.close(); await store.delete(); await api.post('/auth/logout')
})
