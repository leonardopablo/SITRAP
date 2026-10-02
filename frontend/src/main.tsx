import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from './App'
import './styles.css'
import { AuthProvider } from './auth/AuthProvider'
import { WorkspaceProvider } from './auth/workspace'
import { registerWorker } from './pwa'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1 } } })
void registerWorker()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter><AuthProvider><WorkspaceProvider><App /></WorkspaceProvider></AuthProvider></BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
