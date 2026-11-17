import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowRight, Bot, BrainCircuit, CheckCircle2, ChevronRight, CloudOff, Database,
  Layers3, LoaderCircle, LockKeyhole, MessageSquareText, Play, ScanSearch, Send,
  ShieldCheck, Sparkles, User, Zap,
} from 'lucide-react'
import { api, timeLabel } from '../lib/api.js'
import { CategoryBadge, EmptyState, SectionHeading, StatusBadge, StepState } from '../components/ui.jsx'

const mayaIntroduction = 'My name is Maya. I am a software engineer with three years of experience. I want to transition into AI engineering within six months. I can study five hours per week.'

export default function Playground({ sessions, health, refresh, notify }) {
  const [selected, setSelected] = useState('agent-a')
  const [histories, setHistories] = useState({})
  const [runs, setRuns] = useState({})
  const [inputs, setInputs] = useState({})
  const [sending, setSending] = useState(false)
  const chatScroll = useRef(null)

  const agents = sessions.length ? sessions : [
    { id: 'agent-a', name: 'Agent A', role: 'Personal assistant', description: 'General personal context and planning.' },
    { id: 'agent-b', name: 'Agent B', role: 'Learning strategist', description: 'Independent session, same authorized memory.' },
  ]
  const selectedAgent = agents.find((agent) => agent.id === selected) || agents[0]
  const currentRun = runs[selected]
  const currentHistory = histories[selected] || []
  const outage = Boolean(health?.provider?.outage_simulated)

  const loadHistories = useCallback(async () => {
    if (!sessions.length) return
    const results = await Promise.all(sessions.map(async (agent) => {
      const data = await api.messages(agent.id)
      return [agent.id, data.messages || []]
    }))
    setHistories(Object.fromEntries(results))
  }, [sessions])

  useEffect(() => {
    loadHistories().catch((error) => notify(error.message, 'error'))
  }, [loadHistories, notify])

  useEffect(() => {
    if (chatScroll.current) chatScroll.current.scrollTop = chatScroll.current.scrollHeight
  }, [currentHistory.length, selected, sending])

  async function sendMessage(preset) {
    const message = (typeof preset === 'string' ? preset : inputs[selected] || '').trim()
    if (!message || sending) return
    const sessionId = selected
    setSending(true)
    setInputs((previous) => ({ ...previous, [sessionId]: '' }))
    setHistories((previous) => ({
      ...previous,
      [sessionId]: [...(previous[sessionId] || []), { id: `pending-${Date.now()}`, role: 'user', content: message, created_at: new Date().toISOString() }],
    }))
    try {
      const result = await api.chat(sessionId, message)
      setRuns((previous) => ({ ...previous, [sessionId]: result }))
      await loadHistories()
      await refresh()
    } catch (error) {
      notify(error.message, 'error')
      setInputs((previous) => ({ ...previous, [sessionId]: message }))
      await loadHistories().catch(() => {})
    } finally {
      setSending(false)
    }
  }

  function switchAgent(id) {
    if (!sending) setSelected(id)
  }

  return (
    <div className="playground-page">
      <SectionHeading
        eyebrow="SHARED MEMORY · ISOLATED HISTORIES"
        title="Agent Playground"
        description="Two independent agents. One authorized memory layer. No repeated onboarding."
        action={<div className="shared-vault-chip"><Database size={15} /><span>Shared vault</span><StatusBadge status={health?.memory?.status || 'standby'}>{health?.memory?.status === 'online' ? 'Connected' : 'Connecting'}</StatusBadge></div>}
      />

      <div className="demo-script">
        <div className="demo-script-title"><Play size={15} fill="currentColor" /><span>CONTINUITY DEMO</span></div>
        <div className="demo-script-step"><span>01</span><p>Share context with <strong>Agent A</strong></p></div><ChevronRight size={15} />
        <div className="demo-script-step"><span>02</span><p>Ask <strong>Agent B</strong> for a plan</p></div><ChevronRight size={15} />
        <div className="demo-script-step"><span>03</span><p>Go offline. <strong>Keep your context.</strong></p></div>
      </div>

      <div className="agent-tabs" role="tablist" aria-label="Agent sessions">
        {agents.map((agent, index) => (
          <button key={agent.id} role="tab" aria-selected={selected === agent.id} className={`agent-tab ${selected === agent.id ? 'active' : ''}`} onClick={() => switchAgent(agent.id)} disabled={sending}>
            <div className={`agent-avatar ${index === 1 ? 'agent-avatar-alt' : ''}`}><Bot size={19} /></div>
            <div><strong>{agent.name}</strong><span>{agent.role}</span></div>
            <span className="session-status"><i /> {index === 1 ? 'Same memory' : 'Connected'}</span>
            {selected === agent.id && <span className="active-session-label">ACTIVE SESSION</span>}
          </button>
        ))}
        <div className="agent-tab-separator"><LockKeyhole size={14} /><span>Conversation histories stay separate</span></div>
      </div>

      <div className="playground-grid">
        <section className="panel chat-panel">
          <div className="chat-header">
            <div><span className="chat-agent-icon"><MessageSquareText size={18} /></span><div><h3>{selectedAgent.name}</h3><p>{selectedAgent.description}</p></div></div>
            <span className={`provider-chip provider-${outage ? 'offline' : health?.provider?.status || 'standby'}`}>{outage ? <CloudOff size={13} /> : <Zap size={13} />}{outage ? 'Memory-only mode' : health?.provider?.configured ? health.provider.model : 'Transparent local mode'}</span>
          </div>

          <div className="chat-messages" ref={chatScroll}>
            {!currentHistory.length && !sending ? (
              <div className="chat-empty">
                <div className="chat-empty-symbol"><BrainCircuit size={28} strokeWidth={1.4} /></div>
                <h3>{selected === 'agent-a' ? 'Start with something worth remembering.' : 'A new session. Not a blank slate.'}</h3>
                <p>{selected === 'agent-a' ? 'Share a durable goal or preference. Memora will extract it into your user-owned vault.' : 'This agent has no access to Agent A’s chat history. It retrieves only your authorized Memora context.'}</p>
                <button className="prompt-card" onClick={() => sendMessage(selected === 'agent-a' ? mayaIntroduction : outage ? 'What is my career goal?' : 'Create a learning plan for me.')}>
                  <span className="prompt-card-label"><Sparkles size={13} /> TRY THE DEMO</span>
                  <span>{selected === 'agent-a' ? mayaIntroduction : outage ? 'What is my career goal?' : 'Create a learning plan for me.'}</span>
                  <ArrowRight size={17} />
                </button>
              </div>
            ) : (
              <div className="message-list">
                {currentHistory.map((message) => (
                  <div key={message.id} className={`message-row message-${message.role}`}>
                    <div className="message-avatar">{message.role === 'user' ? <User size={15} /> : <Bot size={15} />}</div>
                    <div className="message-wrap">
                      <div className="message-meta"><strong>{message.role === 'user' ? 'Maya' : selectedAgent.name}</strong><span>{timeLabel(message.created_at)}</span>{message.role === 'assistant' && message.provider && <span className="message-provider">{providerName(message.provider)}</span>}</div>
                      <div className="message-bubble"><MessageContent content={message.content} /></div>
                    </div>
                  </div>
                ))}
                {sending && <div className="message-row message-assistant"><div className="message-avatar"><Bot size={15} /></div><div className="message-wrap"><div className="message-meta"><strong>{selectedAgent.name}</strong><span>Harness running</span></div><div className="message-bubble thinking-bubble"><LoaderCircle size={16} className="spin" /><span>{outage ? 'Retrieving directly from Memora…' : 'Retrieving context and preparing a response…'}</span></div></div></div>}
              </div>
            )}
          </div>

          <div className="chat-composer-wrap">
            <div className="composer-context-note"><ScanSearch size={14} /><span>Every message checks Memora before model invocation</span></div>
            <div className="chat-composer">
              <textarea
                rows={2}
                value={inputs[selected] || ''}
                onChange={(event) => setInputs((previous) => ({ ...previous, [selected]: event.target.value }))}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder={outage ? 'Ask for saved context—no model required…' : `Message ${selectedAgent.name}…`}
                disabled={sending}
              />
              <button className="send-button" onClick={() => sendMessage()} disabled={sending || !(inputs[selected] || '').trim()} aria-label="Send message">{sending ? <LoaderCircle size={17} className="spin" /> : <Send size={17} />}</button>
            </div>
            <div className="composer-footer"><span>Enter to send · Shift + Enter for a new line</span><span><ShieldCheck size={12} /> Retrieval works without AI</span></div>
          </div>
        </section>

        <aside className="context-sidebar">
          <section className="panel retrieved-panel">
            <div className="context-panel-header"><div><Layers3 size={17} /><h3>Retrieved from Memora</h3></div><span>{currentRun?.memories_retrieved?.length || 0} RECORDS</span></div>
            <p className="context-panel-description">Actual records injected into {selectedAgent.name}’s latest run.</p>
            <div className="retrieved-list">
              {currentRun?.memories_retrieved?.map((memory, index) => (
                <div className="retrieved-memory" key={memory.id}>
                  <div className="retrieved-memory-top"><CategoryBadge>{memory.category}</CategoryBadge><span>#{String(index + 1).padStart(2, '0')}</span></div>
                  <p>{memory.content}</p>
                  <div className="retrieval-reason"><ScanSearch size={12} /><span>{memory.reason}</span></div>
                  <small>{memory.id} · {memory.source_agent}</small>
                </div>
              ))}
              {!currentRun && <EmptyState icon={ScanSearch} title="No run yet">Send a message to see exactly which memories this agent retrieves.</EmptyState>}
              {currentRun && !currentRun.memories_retrieved?.length && <EmptyState icon={Database} title="No relevant memories">This run proceeded without injecting stored context.</EmptyState>}
            </div>
            {currentRun && <div className={`invocation-result invocation-${currentRun.provider_used}`}>
              {currentRun.model_invoked ? <Zap size={16} /> : <Database size={16} />}
              <div><strong>{currentRun.model_invoked ? `${providerName(currentRun.provider_used)} model invoked` : 'No model invocation required'}</strong><span>{currentRun.provider_used === 'memory-only' ? 'Primary provider bypassed · SQLite retrieval' : currentRun.provider_used === 'local' ? 'Transparent deterministic fallback' : 'Response generated with retrieved context'}</span></div>
            </div>}
          </section>

          <section className="panel trace-panel">
            <div className="context-panel-header"><div><BrainCircuit size={17} /><h3>Harness trace</h3></div>{currentRun && <span className="trace-live">OBSERVABLE</span>}</div>
            {currentRun ? <div className="trace-list">
              {currentRun.trace?.map((step, index) => <div className={`trace-row trace-row-${step.status}`} key={`${step.step}-${index}`}><StepState status={step.status} /><div><strong>{step.label || step.step}</strong><p>{step.detail}</p></div></div>)}
            </div> : <div className="trace-placeholder"><span>USER INPUT</span><i /><span>RETRIEVAL</span><i /><span>VALIDATION</span><i /><span>MODEL / FALLBACK</span><i /><span>MEMORY UPDATE</span></div>}
            {currentRun?.memories_saved?.length > 0 && <div className="saved-run-summary"><CheckCircle2 size={15} /><span>{currentRun.memories_saved.length} new {currentRun.memories_saved.length === 1 ? 'memory' : 'memories'} persisted after this run</span></div>}
          </section>
        </aside>
      </div>
    </div>
  )
}

function MessageContent({ content }) {
  return String(content).split('\n').map((line, index) => {
    if (!line.trim()) return <div className="message-space" key={index} />
    if (/^\s*[-•]\s+/.test(line)) {
      return <div className="formatted-bullet" key={index}><span>•</span><p>{inlineText(line.replace(/^\s*[-•]\s+/, ''))}</p></div>
    }
    return <p className="formatted-line" key={index}>{inlineText(line)}</p>
  })
}

function inlineText(line) {
  return line.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) => (
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={index}>{part.slice(2, -2)}</strong>
      : <React.Fragment key={index}>{part}</React.Fragment>
  ))
}

function providerName(provider) {
  return ({ primary: 'Primary model', backup: 'Backup model', local: 'Local fallback', 'memory-only': 'Memory only' })[provider] || provider
}
