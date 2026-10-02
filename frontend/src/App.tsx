import { Link, Route, Routes } from 'react-router-dom'
import { Logo } from './components/Logo'
import { Illustration } from './components/Illustration'

export function App() {
  return <>
    <a className="skip-link" href="#contenido">Saltar al contenido</a>
    <header><Link to="/" aria-label="SITRAP, inicio"><Logo /></Link></header>
    <main id="contenido" tabIndex={-1}>
      <Routes>
        <Route path="/" element={<section className="card form"><Illustration kind="route" /><h1>Cada producto tiene una historia</h1><p>Seguimos el camino de la leche, desde su origen.</p><Link className="button" to="/acceso">Ingresar</Link></section>} />
        <Route path="/acceso" element={<><h1>Acceso a SITRAP</h1><p>El acceso estará disponible al implementar F05.</p><Link to="/">Volver al inicio</Link></>} />
        <Route path="*" element={<><h1>Página no encontrada</h1><Link to="/">Volver al inicio</Link></>} />
      </Routes>
    </main>
  </>
}
