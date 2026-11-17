import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity, Bot, Box, ChevronRight, CloudOff, Database, LayoutDashboard,
  MemoryStick, MessagesSquare, ShieldCheck,
} from 'lucide-react'
import { api, providerLabel } from './lib/api.js'
import Overview from './screens/Overview.jsx'
import MemoryVault from './screens/MemoryVault.jsx'
import Playground from './screens/Playground.jsx'
import Resilience from './screens/Resilience.jsx'
import { StatusBadge, StatusDot, Toast } from './components/ui.jsx'

const navigation = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, caption: 'System at a glance' },
  { id: 'vault', label: 'Memory Vault', icon: Database, caption: 'User-owned context' },
  { id: 'playground', label: 'Agent Playground', icon: MessagesSquare, caption: 'Shared memory, separate sessions' },
  { id: 'resilience', label: 'Resilience Console', icon: ShieldCheck, caption: 'Outage & recovery controls' },
]

export default function App() {
  const [view, setView] = useState('overview')
  const [health, setHealth] = useState(null)
  const [memories, setMemories] = useState([])
  const [events, setEvents] = useState([])
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [backendError, setBackendError] = useState('')
  const [actionBusy, setActionBusy] = useState(false)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  const notify = useCallback((message, tone = 'success') => {
    clearTimeout(toastTimer.current)
    setToast({ message, tone })
    toastTimer.current = setTimeout(() => setToast(null), 4500)
  }, [])

  const refresh = useCallback(async (includeSessions = true) => {
    const requests = [api.health(), api.listMemories(), api.events(50)]
    if (includeSessions) requests.push(api.sessions())
    const [healthData, memoryData, eventData, sessionData] = await Promise.all(requests)
    setHealth(healthData)
    setMemories(memoryData.memories || [])
    setEvents(eventData.events || [])
    if (sessionData) setSessions(sessionData.sessions || [])
    setBackendError('')
  }, [])

  useEffect(() => {
    refresh().catch((error) => setBackendError(error.message)).finally(() => setLoading(false))
    const interval = setInterval(() => {
      Promise.all([api.health(), api.events(50)])
        .then(([healthData, eventData]) => {
          setHealth(healthData)
          setEvents(eventData.events || [])
          setBackendError('')
        })
        .catch((error) => setBackendError(error.message))
    }, 7000)
    return () => {
      clearInterval(interval)
      clearTimeout(toastTimer.current)
    }
  }, [refresh])

  async function toggleProvider() {
    if (!health || actionBusy) return
    setActionBusy(true)
    const isOutage = health.provider?.outage_simulated
    try {
      const data = isOutage ? await api.restore() : await api.outage()
      setHealth(data)
      const eventData = await api.events(50)
      setEvents(eventData.events || [])
      notify(isOutage ? 'Primary provider restored. Existing context is unchanged.' : 'Provider blocked. Memora retrieval remains operational.', 'info')
    } catch (error) {
      notify(error.message, 'error')
    } finally {
      setActionBusy(false)
    }
  }

  async function refreshAfterAction(message) {
    try {
      await refresh()
      if (message) notify(message)
    } catch (error) {
      notify(error.message, 'error')
    }
  }

  const current = navigation.find((item) => item.id === view)
  const outage = Boolean(health?.provider?.outage_simulated)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setView('overview')} aria-label="Memora overview">
          <span className="brand-mark"><Box size={19} strokeWidth={1.8} /></span>
          <span className="brand-name">memora<span>.</span></span>
        </button>
        <div className="workspace-switcher">
          <div className="workspace-avatar">MC</div>
          <div className="workspace-copy"><strong>Maya’s workspace</strong><span>Personal · Local</span></div>
          <ChevronRight size={14} />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="main-navigation" aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => setView(id)} title={label}>
              <Icon size={18} strokeWidth={1.7} />
              <span>{label}</span>
              {id === 'resilience' && outage && <span className="nav-alert" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-system">
          <div className="nav-caption">SYSTEM</div>
          <div className="side-status-row"><span><StatusDot status={health?.memory?.status === 'online' ? 'online' : 'standby'} />Memory store</span><strong>{health?.memory?.status === 'online' ? 'Local' : 'Connecting'}</strong></div>
          <div className="side-status-row"><span><StatusDot status={health?.provider?.status || 'standby'} />Primary model</span><strong>{providerLabel(health)}</strong></div>
          <div className="ownership-note"><ShieldCheck size={15} /><span>Your context.<br />Your control.</span></div>
        </div>
        <div className="sidebar-profile">
          <div className="profile-avatar">M</div>
          <div><strong>Maya Chen</strong><span>Owner · user</span></div>
          <Activity size={15} />
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="page-identity"><h1>{current.label}</h1><span>{current.caption}</span></div>
          <div className="topbar-right">
            <span className="local-environment"><MemoryStick size={14} /> LOCAL WORKSPACE</span>
            <StatusBadge status={outage ? 'offline' : health?.memory?.status || 'standby'}>
              {outage ? 'Memory-only resilience' : 'Context protected'}
            </StatusBadge>
          </div>
        </header>

        {outage && (
          <div className="outage-banner">
            <div><CloudOff size={18} /><strong>Controlled provider outage active</strong><span>Primary model calls are blocked. Your local memory is still available.</span></div>
            <button onClick={toggleProvider} disabled={actionBusy}>Restore provider</button>
          </div>
        )}
        {backendError && (
          <div className="backend-banner"><Bot size={17} /><span>Memora API unavailable: {backendError}. Start the FastAPI service on port 8000.</span></div>
        )}

        <div className={`page-content ${loading ? 'page-loading' : ''}`}>
          {view === 'overview' && <Overview health={health} memories={memories} sessions={sessions} events={events} onNavigate={setView} onToggleProvider={toggleProvider} actionBusy={actionBusy} />}
          {view === 'vault' && <MemoryVault memories={memories} refresh={refreshAfterAction} notify={notify} />}
          {view === 'playground' && <Playground sessions={sessions} health={health} refresh={refreshAfterAction} notify={notify} />}
          {view === 'resilience' && <Resilience health={health} events={events} onToggleProvider={toggleProvider} actionBusy={actionBusy} refresh={refreshAfterAction} notify={notify} />}
        </div>
        <footer className="app-footer"><span>MEMORA / CONTEXT CONTINUITY LAYER</span><span>Models change. Context remains.</span></footer>
      </main>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  )
}
