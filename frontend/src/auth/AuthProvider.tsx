import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'
import type { Account } from '../api/types'

interface AuthState {
  account: Account | null; loading: boolean; expiredAccount: Account | null; error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  changePassword: (current: string, next: string) => Promise<void>
  refresh: () => Promise<void>
}
const Context = createContext<AuthState | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const cache = useQueryClient()
  const [account, setAccount] = useState<Account | null>(null)
  const [expiredAccount, setExpiredAccount] = useState<Account | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  async function refresh() {
    setLoading(true)
    try { setAccount(await api.request<Account>('/auth/me')); setError(null) }
    catch (e) { if (!(e instanceof ApiError && e.status === 401)) setError('No pudimos comprobar la sesión. Reintenta con conexión.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void refresh() }, [])
  useEffect(() => {
    const expire = () => { if (account) setExpiredAccount(account); setAccount(null); cache.clear() }
    window.addEventListener('sitrap:session-expired', expire)
    return () => window.removeEventListener('sitrap:session-expired', expire)
  }, [account, cache])
  async function login(username: string, password: string) {
    if (expiredAccount && username !== expiredAccount.username) throw new Error(`Continúa con la cuenta ${expiredAccount.username}.`)
    await api.refreshCsrf()
    await api.post('/auth/login', { username, password })
    await api.refreshCsrf()
    const next = await api.request<Account>('/auth/me')
    if (expiredAccount && next.id !== expiredAccount.id) { await api.post('/auth/logout'); throw new Error('La cuenta no coincide con la sesión pendiente.') }
    cache.clear(); setAccount(next); setExpiredAccount(null); setError(null)
  }
  async function logout() {
    await api.post('/auth/logout')
    cache.clear(); setAccount(null); setExpiredAccount(null)
  }
  async function changePassword(current: string, next: string) {
    await api.post('/auth/change-password', { current_password: current, new_password: next })
    await api.refreshCsrf()
    setAccount(await api.request<Account>('/auth/me'))
  }
  return <Context.Provider value={{ account, loading, expiredAccount, error, login, logout, changePassword, refresh }}>{children}</Context.Provider>
}
export function useAuth() {
  const state = useContext(Context)
  if (!state) throw new Error('AuthProvider requerido')
  return state
}
