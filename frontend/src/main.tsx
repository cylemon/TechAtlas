import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// React Flow 的基础样式必须排在 index.css 之前：
// 组件外观主要由 Tailwind 决定，让 Tailwind 的规则后加载以便覆盖
import '@xyflow/react/dist/style.css'
import './index.css'

import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <App />
    </StrictMode>,
)
