import { Link, Route, Routes } from 'react-router-dom'

export function App() {
  return <>
    <header><Link to="/">SITRAP</Link></header>
    <main>
      <Routes>
        <Route path="/" element={<><h1>Cada producto tiene una historia</h1><p>Seguimos el camino de la leche, desde su origen.</p><Link to="/acceso">Ingresar</Link></>} />
        <Route path="/acceso" element={<><h1>Acceso a SITRAP</h1><p>El acceso estará disponible al implementar F05.</p><Link to="/">Volver al inicio</Link></>} />
        <Route path="*" element={<><h1>Página no encontrada</h1><Link to="/">Volver al inicio</Link></>} />
      </Routes>
    </main>
  </>
}
