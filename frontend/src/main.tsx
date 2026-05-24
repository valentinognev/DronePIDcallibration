import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// #region agent log
window.addEventListener('error', (ev) => {
  fetch('http://127.0.0.1:7808/ingest/b08aba62-617c-4296-b2d6-97342ac54eb4',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'93a084'},body:JSON.stringify({sessionId:'93a084',location:'main.tsx:error',message:'uncaught error',data:{msg:ev.message,filename:ev.filename,lineno:ev.lineno},timestamp:Date.now(),hypothesisId:'H4'})}).catch(()=>{});
});
window.addEventListener('unhandledrejection', (ev) => {
  fetch('http://127.0.0.1:7808/ingest/b08aba62-617c-4296-b2d6-97342ac54eb4',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'93a084'},body:JSON.stringify({sessionId:'93a084',location:'main.tsx:rejection',message:'unhandled rejection',data:{reason:String(ev.reason)},timestamp:Date.now(),hypothesisId:'H4'})}).catch(()=>{});
});
// #endregion

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
