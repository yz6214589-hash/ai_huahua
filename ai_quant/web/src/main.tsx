import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { DataStatusProvider } from './context/DataStatusContext'
import './index.css'
// @bytemd 研报查看器样式
import 'bytemd/dist/index.css'
import 'highlight.js/styles/github.css'
import 'katex/dist/katex.min.css'
// 自定义研报排版增强样式（覆盖 bytemd 默认 + Tailwind preflight reset）
import './report-viewer.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DataStatusProvider>
      <App />
    </DataStatusProvider>
  </StrictMode>,
)
