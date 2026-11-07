import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { Splash } from './components/Splash.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <Splash />
  </StrictMode>,
)
