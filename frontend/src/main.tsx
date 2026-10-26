import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
// Токены и шрифты подключает app.css: Tailwind должен обработать их в одном проходе
import './styles/app.css'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('Root container #root is missing in index.html')
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
