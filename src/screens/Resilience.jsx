import React, { useState } from 'react'
import {
  ArrowRight, Check, CheckCircle2, Circle, Database, FileClock, FlaskConical,
  HardDrive, LoaderCircle, Play, PlugZap, RotateCcw, ScanSearch, ServerOff,
  ShieldCheck, TerminalSquare, Unplug, Workflow, Zap,
} from 'lucide-react'
import { api, timeLabel } from '../lib/api.js'
import { CategoryBadge, SectionHeading, StatusBadge, StatusDot } from '../components/ui.jsx'

export default function Resilience({ health, events, onToggleProvider, actionBusy, refresh, notify }) {
  const [query, setQuery] = useState('What is my career goal?')
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState(null)
  const outage = Boolean(health?.provider?.outage_simulated)

  async function testRetrieval() {
    if (!query.trim() || testing) return
    setTesting(true)
    try {
      const data = await api.retrieve(query.trim())
      setResult(data)
      await refresh()
      notify(`Recovered ${data.count} memories without invoking a model.`)
    } catch (error) {
      notify(error.message, 'error')
    } finally {
      setTesting(false)
    }
  }

  const providerStatus = health?.provider?.status || 'standby'
  const providerText = outage ? 'Offline' : providerStatus === 'online' ? 'Online' : providerStatus === 'standby' ? 'Standby' : providerStatus

  return (
    <div className="resilience-page">
      <SectionHeading
        eyebrow="CONTROLLED FAILURE · VERIFIABLE RECOVERY"
        title="Resilience Console"
        description="Disconnect the primary model—not the backend—and prove your context has an independent lifeline."
        action={<StatusBadge status={outage ? 'offline' : 'online'}>{outage ? 'OUTAGE SIMULATION ACTIVE' : 'ALL CORE SERVICES OPERATIONAL'}</StatusBadge>}
      />

      <div className="resilience-disclaimer"><FlaskConical size={16} /><span>This is a controlled, local simulation of provider unavailability. It does not claim or create a real external outage.</span></div>

      <section className={`resilience-control panel ${outage ? 'control-outage' : ''}`}>
        <div className="failure-architecture">
          <div className="failure-service provider-service">
            <div className="failure-service-top"><span className="service-icon"><Zap size={21} /></span><StatusBadge status={providerStatus}>{providerText}</StatusBadge></div>
            <span className="service-eyebrow">PRIMARY INTELLIGENCE</span>
            <h3>{health?.provider?.name || 'AI Provider'}</h3>
            <p>{health?.provider?.configured ? health.provider.model : 'Awaiting optional API credentials'}</p>
            <div className="service-detail"><span>Request path</span><strong>{outage ? 'BLOCKED BY SERVER' : health?.provider?.configured ? 'ENABLED' : 'LOCAL FALLBACK'}</strong></div>
          </div>

          <div className="failure-link">
            <span className={`link-line ${outage ? 'line-cut' : ''}`}><i /><i /><i /></span>
            <div className={`link-label ${outage ? 'cut' : ''}`}>{outage ? <ServerOff size={18} /> : <Workflow size={18} />}<span>{outage ? 'MODEL PATH SEVERED' : 'INTERCHANGEABLE PROVIDER'}</span></div>
            <span className={`link-line ${outage ? 'line-cut' : ''}`}><i /><i /><i /></span>
          </div>

          <div className="failure-service memory-service">
            <div className="failure-service-top"><span className="service-icon"><Database size={21} /></span><StatusBadge status={health?.memory?.status || 'standby'}>{health?.memory?.status === 'online' ? 'Online' : 'Connecting'}</StatusBadge></div>
            <span className="service-eyebrow">PERSISTENT CONTEXT</span>
            <h3>Memora Memory Vault</h3>
            <p>Independent SQLite · User-owned</p>
            <div className="service-detail"><span>Context retrieval</span><strong>{health?.retrieval?.status === 'operational' ? 'OPERATIONAL' : 'CHECKING'}</strong></div>
          </div>
        </div>
        <div className="outage-actions">
          <div><strong>{outage ? 'Primary provider is disconnected.' : 'Ready to test continuity?'}</strong><span>{outage ? 'The API and database are still running. Retrieve context below or return to the Agent Playground.' : 'We’ll gate the primary model request path on the backend while preserving all memory services.'}</span></div>
          <button className={`button outage-button ${outage ? 'restore-button' : ''}`} onClick={onToggleProvider} disabled={actionBusy || !health}>
            {actionBusy ? <LoaderCircle size={17} className="spin" /> : outage ? <RotateCcw size={17} /> : <Unplug size={17} />}
            {actionBusy ? 'Updating service state…' : outage ? 'Restore Provider' : 'Simulate Provider Outage'}
          </button>
        </div>
      </section>

      <div className="resilience-grid">
        <section className="panel retrieval-tester">
          <div className="panel-header"><div><h3>LLM-free retrieval test</h3><p>Read directly from the memory layer. No generation involved.</p></div><span className="mono-tag"><ScanSearch size={13} /> POST /memory/retrieve</span></div>
          <div className="retrieval-test-body">
            <label className="test-query"><span>CONTEXT QUERY</span><div><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && testRetrieval()} placeholder="What do you need to recover?" /><button className="button button-primary" onClick={testRetrieval} disabled={testing || !query.trim()}>{testing ? <LoaderCircle size={16} className="spin" /> : <Play size={15} fill="currentColor" />}{testing ? 'Reading vault…' : 'Retrieve context'}</button></div></label>
            <div className="quick-queries"><span>Try:</span>{['What is my career goal?', 'Create a learning plan for me', 'What do you know about me?'].map((item) => <button key={item} onClick={() => setQuery(item)}>{item}</button>)}</div>

            {result ? <div className="retrieval-result">
              <div className="retrieval-result-head"><div><CheckCircle2 size={17} /><strong>Context recovered successfully</strong></div><div><span>{result.elapsed_ms} ms</span><i /><span>{result.count} records</span><i /><span>0 model calls</span></div></div>
              <div className="recovered-records">
                {result.memories.map((memory, index) => <div className="recovered-record" key={memory.id}><span className="recovered-index">{String(index + 1).padStart(2, '0')}</span><div><p>{memory.content}</p><div><CategoryBadge>{memory.category}</CategoryBadge><span>{memory.reason}</span><code>{memory.id}</code></div></div></div>)}
                {!result.memories.length && <div className="no-recovery"><ScanSearch size={20} /><strong>No relevant records found</strong><p>Try the Agent Playground to add Maya’s demo context first.</p></div>}
              </div>
              <div className="retrieval-proof"><HardDrive size={14} /><span>Source: Memora SQLite</span><ArrowRight size={13} /><span>Deterministic ranking</span><ArrowRight size={13} /><strong>No model invocation</strong></div>
            </div> : <div className="retrieval-idle"><ScanSearch size={25} strokeWidth={1.4} /><strong>Make continuity observable.</strong><p>Run a retrieval test before or during the outage. The response will include real records and match reasons.</p></div>}
          </div>
        </section>

        <section className="panel guarantees-panel">
          <div className="panel-header"><div><h3>Continuity guarantees</h3><p>What remains true when intelligence is unavailable</p></div><ShieldCheck size={18} /></div>
          <div className="guarantee-list">
            <div><span className="guarantee-icon"><Check size={15} /></span><div><strong>Persistent storage</strong><p>Local SQLite reads and writes are independent from the model provider.</p></div><span className="guarantee-state">ALWAYS ON</span></div>
            <div><span className="guarantee-icon"><Check size={15} /></span><div><strong>Context retrieval</strong><p>Keyword and category matching run entirely in the Memora backend.</p></div><span className="guarantee-state">NO LLM</span></div>
            <div><span className="guarantee-icon"><Check size={15} /></span><div><strong>User ownership</strong><p>Inspecting, correcting, exporting and deleting do not require generation.</p></div><span className="guarantee-state">USER CONTROL</span></div>
            <div className={outage ? 'guarantee-verified' : ''}><span className="guarantee-icon">{outage ? <Check size={15} /> : <Circle size={12} />}</span><div><strong>Provider request gate</strong><p>{outage ? 'Backend is actively blocking primary model requests.' : 'Activate the simulation to enforce the server-side request gate.'}</p></div><span className="guarantee-state">{outage ? 'ENFORCED' : 'READY'}</span></div>
          </div>
          <div className="backup-note"><PlugZap size={16} /><div><strong>Optional backup model</strong><p>{health?.backup?.configured ? 'Configured and available for resilient generation.' : 'Not configured. Memora will transparently use deterministic memory-only output.'}</p></div></div>
        </section>
      </div>

      <section className="panel event-console">
        <div className="event-console-header"><div><TerminalSquare size={17} /><h3>Runtime event log</h3><span>REAL APPLICATION EVENTS</span></div><div><StatusDot status="online" pulse /> LIVE</div></div>
        <div className="event-console-columns"><span>TIME</span><span>LEVEL</span><span>EVENT</span><span>SOURCE</span></div>
        <div className="event-console-body">
          {events.slice(0, 18).map((event) => <div className="event-console-row" key={event.id}><time>{timeLabel(event.timestamp)}</time><span className={`event-level event-${event.level}`}>{event.level.toUpperCase()}</span><p>{event.message}</p><code>{event.agent_id || event.event_type}</code></div>)}
          {!events.length && <div className="console-empty">Waiting for Memora runtime events…</div>}
        </div>
        <div className="event-console-footer"><span>Latest {Math.min(events.length, 18)} events · persisted locally</span><span><FileClock size={13} /> UTC timestamps</span></div>
      </section>
    </div>
  )
}
