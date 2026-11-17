import React from 'react'
import {
  ArrowRight, Bot, CheckCircle2, CloudOff, Database, GitBranch,
  ListTree, RefreshCw, ShieldCheck, Target, Unplug, Zap,
} from 'lucide-react'
import { CategoryBadge, EmptyState, StatusBadge, StatusDot } from '../components/ui.jsx'
import { relativeTime, timeLabel } from '../lib/api.js'

export default function Overview({ health, memories, sessions, events, onNavigate, onToggleProvider, actionBusy }) {
  const activeMemories = memories.filter((memory) => memory.status === 'active')
  const goals = activeMemories.filter((memory) => memory.category === 'goals')
  const conflicts = memories.filter((memory) => memory.conflict_status === 'pending')
  const outage = Boolean(health?.provider?.outage_simulated)
  const recent = memories.slice(0, 5)

  return (
    <div className="overview-page">
      <section className="overview-hero">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-line" /> CONTEXT CONTINUITY INFRASTRUCTURE</div>
          <h2>Your AI can go offline.<br /><span>Your context shouldn’t.</span></h2>
          <p>One user-owned memory layer for every agent. Preserve goals, decisions and preferences beyond sessions, models and providers.</p>
          <div className="hero-actions">
            <button className="button button-primary" onClick={() => onNavigate('playground')}>Run continuity demo <ArrowRight size={16} /></button>
            <button className="button button-secondary" onClick={() => onNavigate('vault')}><Database size={15} /> Explore memory</button>
          </div>
          <div className="hero-proof"><ShieldCheck size={15} /><span>Local-first SQLite</span><i /> <span>No model required for retrieval</span></div>
        </div>
        <div className={`continuity-map ${outage ? 'map-outage' : ''}`}>
          <div className="map-header"><span>LIVE CONTEXT PATH</span><StatusBadge status={outage ? 'offline' : 'online'}>{outage ? 'Resilient mode' : 'Operational'}</StatusBadge></div>
          <div className="map-flow">
            <div className="map-node agent-node"><div className="map-icon"><Bot size={20} /></div><div><span>AI AGENTS</span><strong>Agent A <i>+</i> Agent B</strong></div><span className="node-count">{sessions.length || 2}</span></div>
            <div className="map-connector"><span /><div>{outage ? 'direct retrieval' : 'read / write'}</div><span /></div>
            <div className="map-node memory-node"><div className="map-icon"><Database size={20} /></div><div><span>INDEPENDENT LAYER</span><strong>Memora Vault</strong></div><StatusDot status="online" pulse /></div>
          </div>
          <div className="map-provider">
            {outage ? <CloudOff size={16} /> : <GitBranch size={16} />}
            <span>{outage ? 'Primary provider disconnected' : 'Primary provider is interchangeable'}</span>
            <strong>{outage ? 'BLOCKED' : 'NOT REQUIRED'}</strong>
          </div>
        </div>
      </section>

      <section className="stats-strip">
        <div className="stat-cell"><div className="stat-icon"><Database size={18} /></div><div><span>Total memories</span><strong>{memories.length}</strong><small>{activeMemories.length} active records</small></div></div>
        <div className="stat-cell"><div className="stat-icon"><Target size={18} /></div><div><span>Active goals</span><strong>{goals.length}</strong><small>Persistent across agents</small></div></div>
        <div className="stat-cell"><div className="stat-icon"><Bot size={18} /></div><div><span>Connected agents</span><strong>{sessions.length}</strong><small>Separate conversation history</small></div></div>
        <div className="stat-cell"><div className="stat-icon"><ShieldCheck size={18} /></div><div><span>Memory integrity</span><strong className="stat-text">{conflicts.length ? `${conflicts.length} to review` : 'Protected'}</strong><small>{conflicts.length ? 'Conflicts need your decision' : 'No unresolved conflicts'}</small></div></div>
      </section>

      <div className="overview-grid">
        <section className="panel recent-memory-panel">
          <div className="panel-header"><div><h3>Recent memories</h3><p>Latest context saved to your vault</p></div><button className="text-button" onClick={() => onNavigate('vault')}>View all <ArrowRight size={14} /></button></div>
          {recent.length ? <div className="recent-memory-list">
            {recent.map((memory) => (
              <div className="recent-memory" key={memory.id}>
                <div className="memory-type-icon"><ListTree size={16} /></div>
                <div className="recent-memory-copy"><div><CategoryBadge>{memory.category}</CategoryBadge>{memory.is_demo && <span className="demo-label">DEMO</span>}</div><p>{memory.content}</p><span>{memory.source_agent} · {relativeTime(memory.updated_at)}</span></div>
                <span className={`record-status record-${memory.status}`}>{memory.status}</span>
              </div>
            ))}
          </div> : <EmptyState icon={Database} title="Your vault is ready">Share context with an agent to create your first memory.</EmptyState>}
        </section>

        <section className="panel system-health-panel">
          <div className="panel-header"><div><h3>System health</h3><p>Independent service boundaries</p></div><ActivityIcon /></div>
          <div className="health-list">
            <div className="health-row"><div className="health-service-icon"><Zap size={17} /></div><div><strong>Primary AI provider</strong><span>{health?.provider?.configured ? health.provider.model : 'API credentials not configured'}</span></div><StatusBadge status={health?.provider?.status || 'standby'}>{health?.provider?.status === 'standby' ? 'Local mode' : health?.provider?.status || 'Connecting'}</StatusBadge></div>
            <div className="health-row"><div className="health-service-icon"><Database size={17} /></div><div><strong>Memora memory store</strong><span>SQLite · persistent local storage</span></div><StatusBadge status={health?.memory?.status || 'standby'}>{health?.memory?.status === 'online' ? 'Online' : 'Connecting'}</StatusBadge></div>
            <div className="health-row"><div className="health-service-icon"><RefreshCw size={17} /></div><div><strong>Context retrieval</strong><span>Deterministic · LLM-independent</span></div><StatusBadge status={health?.retrieval?.status === 'operational' ? 'online' : 'standby'}>{health?.retrieval?.status || 'Connecting'}</StatusBadge></div>
          </div>
          <div className="health-principle"><CheckCircle2 size={16} /><p>Memory remains accessible when model invocation is unavailable.</p></div>
          <button className={`button resilience-action ${outage ? 'button-secondary' : 'button-primary'}`} onClick={onToggleProvider} disabled={actionBusy || !health}>
            {outage ? <RefreshCw size={16} /> : <Unplug size={16} />}{actionBusy ? 'Updating provider…' : outage ? 'Restore primary provider' : 'Simulate Provider Outage'}
          </button>
          <span className="simulation-caption">Controlled simulation · does not contact an external outage service</span>
        </section>
      </div>

      <section className="panel activity-panel">
        <div className="panel-header"><div><h3>Live activity</h3><p>Actual events from your local Memora runtime</p></div><button className="text-button" onClick={() => onNavigate('resilience')}>Open console <ArrowRight size={14} /></button></div>
        <div className="activity-table">
          {events.slice(0, 6).map((event) => <div className="activity-row" key={event.id}><span className="activity-time">{timeLabel(event.timestamp)}</span><StatusDot status={event.level === 'error' ? 'offline' : event.level === 'warning' ? 'standby' : 'online'} /><span className="activity-message">{event.message}</span><span className="activity-source">{event.agent_id || event.event_type}</span></div>)}
          {!events.length && <div className="muted-empty">Runtime events will appear here.</div>}
        </div>
      </section>
    </div>
  )
}

function ActivityIcon() {
  return <span className="live-indicator"><span /> LIVE</span>
}
