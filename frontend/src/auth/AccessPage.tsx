import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { apiMode } from '../api/client'
import { Button, Field, Notice } from '../components/ui'
import { useAuth } from './AuthProvider'

const loginSchema = z.object({ username: z.string().min(1, 'Escribe tu usuario.'), password: z.string().min(1, 'Escribe tu contraseña.') })
export function AccessPage() {
  const auth = useAuth()
  const location = useLocation()
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const { register, handleSubmit, resetField, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(loginSchema), defaultValues: { username: auth.expiredAccount?.username ?? '', password: '' } })
  const from = typeof location.state?.from === 'string' && /^\/(?!\/)/.test(location.state.from) && !location.state.from.startsWith('/acceso') ? location.state.from : '/hoy'
  if (auth.account) return <Navigate to={auth.account.change_password_required ? '/cuenta/clave' : from} replace />
  return <section className="card form stack">
    <h1>Acceso a SITRAP</h1>
    {auth.expiredAccount && <Notice tone="warning">Tu sesión venció. Ingresa con {auth.expiredAccount.username}; tus operaciones pendientes se conservan.</Notice>}
    {auth.error && <Notice tone="error">{auth.error}<Button variant="secondary" onClick={() => void auth.refresh()}>Reintentar</Button></Notice>}
    {apiMode === 'mock' && <Notice tone="warning">Demostración sin conexión a la API real. Usuarios: produccion, transporte, recepcion o admin. Contraseña de prueba: Demostracion123! (Temporal123! exige cambio). La sesión simulada se pierde al recargar.</Notice>}
    <form className="stack" onSubmit={handleSubmit(async values => { setError(''); try { await auth.login(values.username, values.password) } catch (e) { setError((e as Error).message) } finally { resetField('password') } })}>
      <Field label="Usuario" autoComplete="username" {...register('username')} error={errors.username?.message} readOnly={!!auth.expiredAccount} />
      <Field label="Contraseña" type={show ? 'text' : 'password'} autoComplete="current-password" {...register('password')} error={errors.password?.message} />
      <Button type="button" variant="secondary" aria-pressed={show} onClick={() => setShow(!show)}>{show ? 'Ocultar' : 'Mostrar'} contraseña</Button>
      {error && <Notice tone="error">{error}</Notice>}
      <Button busy={isSubmitting || auth.loading} type="submit">{isSubmitting ? 'Ingresando…' : 'Ingresar'}</Button>
    </form>
    <p className="help">Si olvidaste tu contraseña, contacta al administrador de tu centro. No hay registro público.</p>
  </section>
}

const passwordSchema = z.object({ current: z.string().min(1, 'Escribe tu contraseña actual.'), next: z.string().min(12, 'Usa al menos 12 caracteres.'), repeat: z.string() }).refine(values => values.next === values.repeat, { path: ['repeat'], message: 'Las contraseñas no coinciden.' })
export function PasswordPage() {
  const auth = useAuth()
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(passwordSchema) })
  if (done) return <Navigate to="/hoy" replace />
  return <section className="card form stack"><h1>Cambiar contraseña</h1>
    {auth.account?.change_password_required && <Notice tone="warning">Tu contraseña es temporal. Cámbiala antes de continuar.</Notice>}
    <form className="stack" onSubmit={handleSubmit(async values => { setError(''); try { await auth.changePassword(values.current, values.next); reset(); setDone(true) } catch (e) { setError((e as Error).message) } })}>
      <Field label="Contraseña actual" type="password" autoComplete="current-password" {...register('current')} error={errors.current?.message} />
      <Field label="Nueva contraseña" type="password" autoComplete="new-password" {...register('next')} error={errors.next?.message} />
      <Field label="Repetir nueva contraseña" type="password" autoComplete="new-password" {...register('repeat')} error={errors.repeat?.message} />
      {error && <Notice tone="error">{error}</Notice>}<Button busy={isSubmitting}>Guardar contraseña</Button>
    </form></section>
}
