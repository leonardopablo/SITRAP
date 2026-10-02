import { Link, Route, Routes } from 'react-router-dom'
import { Logo } from './components/Logo'
import { Illustration } from './components/Illustration'
import { AccessPage, PasswordPage } from './auth/AccessPage'
import { RequireAuth } from './auth/RequireAuth'
import { apiMode } from './api/client'
import { Notice } from './components/ui'
import { Shell, TodayPage, PendingFeature } from './components/Shell'
import { RequireRole } from './auth/workspace'
import { PwaControls } from './pwa'
import { SyncPanel } from './offline/SyncPanel'
import { InboxPage } from './notifications/Inbox'
import { AnimalsPage } from './animals/AnimalsPage'
import { MilkingDraftPage } from './milk/MilkingDraftPage'
import { PreparePage } from './transfers/PreparePage'
import { TransferDetailPage } from './transfers/TransferDetailPage'
import { TransportToday } from './transfers/TransportToday'
import { ReceptionToday } from './transfers/ReceptionToday'
import { CorrectionPage } from './corrections/CorrectionPage'
import { CorrectionHistory } from './corrections/CorrectionHistory'

export function App() {
  return <>
    <a className="skip-link" href="#contenido">Saltar al contenido</a>
    <header><Link to="/" aria-label="SITRAP, inicio"><Logo /></Link><PwaControls /></header>
    <main id="contenido" tabIndex={-1}>
      {apiMode === 'mock' && <Notice tone="warning">Modo simulado · Los datos no están guardados en el servidor SITRAP.</Notice>}
      <Routes>
        <Route path="/" element={<section className="card form"><Illustration kind="route" /><h1>Cada producto tiene una historia</h1><p>Seguimos el camino de la leche, desde su origen.</p><Link className="button" to="/acceso">Ingresar</Link></section>} />
        <Route path="/acceso" element={<AccessPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/cuenta/clave" element={<PasswordPage />} />
          <Route element={<Shell />}>
            <Route path="/hoy" element={<TodayPage />} />
            <Route element={<RequireRole roles={['TRANSPORTE']} />}><Route path="/recogidas" element={<TransportToday />} /></Route>
            <Route element={<RequireRole roles={['RECEPCION']} />}><Route path="/recibir" element={<ReceptionToday />} /></Route>
            <Route path="/sincronizacion" element={<SyncPanel />} />
            <Route path="/avisos" element={<InboxPage />} />
            <Route path="/entregas/:id" element={<TransferDetailPage />} />
            <Route path="/correcciones/:id" element={<CorrectionPage />} />
            <Route path="/correcciones" element={<CorrectionHistory />} />
            <Route element={<RequireRole roles={['PRODUCCION']} />}>
              <Route path="/produccion" element={<MilkingDraftPage />} />
              <Route path="/entregas/preparar" element={<PreparePage />} />
              <Route path="/vacas" element={<AnimalsPage />} />
              <Route path="/historial" element={<PendingFeature title="Historial" />} />
            </Route>
            <Route element={<RequireRole roles={['TRANSPORTE']} />}><Route path="/diario" element={<PendingFeature title="Diario de transporte" />} /></Route>
            <Route element={<RequireRole roles={['RECEPCION']} />}><Route path="/recepciones" element={<PendingFeature title="Recepciones" />} /></Route>
            <Route element={<RequireRole roles={['TRANSPORTE', 'RECEPCION']} />}><Route path="/pendientes" element={<CorrectionHistory />} /></Route>
            <Route element={<RequireRole roles={['ADMIN']} />}>
              <Route path="/administracion" element={<PendingFeature title="Administración" />} />
              <Route path="/reportes" element={<PendingFeature title="Reportes" />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<><h1>Página no encontrada</h1><Link to="/">Volver al inicio</Link></>} />
      </Routes>
    </main>
  </>
}
