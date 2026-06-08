import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { DataStatusProvider } from './context/DataStatusContext'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DataStatusProvider>
      <App />
    </DataStatusProvider>
  </StrictMode>,
)
