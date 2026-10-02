import { Link, Route, Routes } from 'react-router-dom'
import { Logo } from './components/Logo'
import { Illustration } from './components/Illustration'
import { AccessPage, PasswordPage } from './auth/AccessPage'
import { RequireAuth } from './auth/RequireAuth'
import { apiMode } from './api/client'
import { Notice } from './components/ui'

export function App() {
  return <>
    <a className="skip-link" href="#contenido">Saltar al contenido</a>
    <header><Link to="/" aria-label="SITRAP, inicio"><Logo /></Link></header>
    <main id="contenido" tabIndex={-1}>
      {apiMode === 'mock' && <Notice tone="warning">Modo simulado · Los datos no están guardados en el servidor SITRAP.</Notice>}
      <Routes>
        <Route path="/" element={<section className="card form"><Illustration kind="route" /><h1>Cada producto tiene una historia</h1><p>Seguimos el camino de la leche, desde su origen.</p><Link className="button" to="/acceso">Ingresar</Link></section>} />
        <Route path="/acceso" element={<AccessPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/cuenta/clave" element={<PasswordPage />} />
          <Route path="/hoy" element={<><h1>Hoy</h1><p>El espacio por roles se incorpora en F06.</p></>} />
        </Route>
        <Route path="*" element={<><h1>Página no encontrada</h1><Link to="/">Volver al inicio</Link></>} />
      </Routes>
    </main>
  </>
}
