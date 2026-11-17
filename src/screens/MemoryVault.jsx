import React, { useMemo, useState } from 'react'
import {
  AlertTriangle, Check, ChevronDown, Clock3, Download, Edit3, FileJson,
  Filter, Plus, Search, ShieldCheck, Trash2,
} from 'lucide-react'
import { api, relativeTime, timeLabel } from '../lib/api.js'
import { CategoryBadge, EmptyState, Modal, SectionHeading } from '../components/ui.jsx'

const categories = ['personal', 'career', 'projects', 'preferences', 'goals', 'decisions', 'commitments', 'work', 'health', 'finance', 'family']
const emptyForm = { content: '', category: 'personal', source_agent: 'memory-explorer', memory_key: '', status: 'active', metadata: {} }

export default function MemoryVault({ memories, refresh, notify }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [status, setStatus] = useState('all')
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const filtered = useMemo(() => memories.filter((memory) => {
    const search = query.toLowerCase().trim()
    const matchesSearch = !search || [memory.content, memory.memory_key, memory.source_agent, memory.id].some((value) => String(value || '').toLowerCase().includes(search))
    return matchesSearch && (category === 'all' || memory.category === category) && (status === 'all' || memory.status === status)
  }), [memories, query, category, status])

  const conflictCount = memories.filter((memory) => memory.conflict_status === 'pending').length
  const demoCount = memories.filter((memory) => memory.is_demo).length

  function openCreate() {
    setForm(emptyForm)
    setModal('create')
  }

  function openEdit(memory) {
    setForm({
      content: memory.content,
      category: memory.category,
      source_agent: memory.source_agent,
      memory_key: memory.memory_key || '',
      status: memory.status,
      metadata: memory.metadata || {},
    })
    setModal(memory)
  }

  async function submit(event) {
    event.preventDefault()
    if (!form.content.trim() || saving) return
    setSaving(true)
    try {
      if (modal === 'create') {
        await api.saveMemory({ ...form, content: form.content.trim(), memory_key: form.memory_key.trim() || null, owner_id: 'user' })
        await refresh('Memory saved to your independent vault.')
      } else {
        await api.updateMemory(modal.id, {
          content: form.content.trim(), category: form.category, status: form.status,
          memory_key: form.memory_key.trim() || null, metadata: form.metadata,
        })
        await refresh('Memory updated.')
      }
      setModal(null)
    } catch (error) {
      notify(error.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function remove(memory) {
    if (!window.confirm(`Permanently delete this memory?\n\n${memory.content}`)) return
    setBusyId(memory.id)
    try {
      await api.deleteMemory(memory.id)
      await refresh('Memory permanently deleted.')
    } catch (error) {
      notify(error.message, 'error')
    } finally {
      setBusyId(null)
    }
  }

  async function resolve(memory) {
    setBusyId(memory.id)
    try {
      await api.resolveMemory(memory.id)
      await refresh('You chose the current record. Other versions were marked superseded.')
    } catch (error) {
      notify(error.message, 'error')
    } finally {
      setBusyId(null)
    }
  }

  async function exportMemories() {
    try {
      const response = await fetch('/api/memory/export?owner_id=user')
      if (!response.ok) throw new Error('Could not export memories')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `memora-export-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      notify(`${memories.length} user-owned records exported as JSON.`)
    } catch (error) {
      notify(error.message, 'error')
    }
  }

  return (
    <div className="vault-page">
      <SectionHeading
        eyebrow="PERSISTENT · PORTABLE · USER-OWNED"
        title="Memory Vault"
        description="The source of truth for your context. Inspect, correct, export or delete every record."
        action={<><button className="button button-secondary" onClick={exportMemories}><Download size={16} /> Export JSON</button><button className="button button-primary" onClick={openCreate}><Plus size={16} /> New memory</button></>}
      />

      <div className="ownership-strip">
        <div className="ownership-strip-icon"><ShieldCheck size={21} /></div>
        <div><strong>Every context has an owner.</strong><p>These records live in your local SQLite vault—not inside a model or a provider account.</p></div>
        <div className="owner-meta"><span>OWNER</span><strong>user</strong></div>
        <div className="owner-meta"><span>STORAGE</span><strong>Local / SQLite</strong></div>
      </div>

      {conflictCount > 0 && <div className="conflict-banner"><AlertTriangle size={18} /><div><strong>{conflictCount} record{conflictCount === 1 ? '' : 's'} need your decision</strong><span>Memora never silently overwrites conflicting context. Choose which version is current.</span></div></div>}

      <section className="panel vault-table-panel">
        <div className="vault-toolbar">
          <label className="search-field"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search content, source or memory ID…" /><kbd>⌘ K</kbd></label>
          <div className="filter-group"><Filter size={15} /><select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter by category"><option value="all">All categories</option>{categories.map((item) => <option value={item} key={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select><ChevronDown size={13} /></div>
          <div className="filter-group"><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter by status"><option value="all">Any status</option><option value="active">Active</option><option value="outdated">Outdated</option><option value="superseded">Superseded</option></select><ChevronDown size={13} /></div>
        </div>
        <div className="table-summary"><span><strong>{filtered.length}</strong> of {memories.length} memories</span>{demoCount > 0 && <span className="demo-summary">Includes {demoCount} clearly marked demo records</span>}</div>
        <div className="table-scroll">
          <table className="memory-table">
            <thead><tr><th>MEMORY</th><th>CATEGORY</th><th>SOURCE</th><th>UPDATED</th><th>STATUS</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {filtered.map((memory) => (
                <React.Fragment key={memory.id}>
                  <tr className={busyId === memory.id ? 'row-busy' : ''}>
                    <td className="memory-content-cell"><div className="memory-content-line"><p>{memory.content}</p>{memory.is_demo && <span className="demo-label">DEMO</span>}</div><span className="memory-id">{memory.id}{memory.memory_key ? ` · ${memory.memory_key}` : ''}</span></td>
                    <td><CategoryBadge>{memory.category}</CategoryBadge></td>
                    <td><div className="source-cell"><span className="source-icon">{memory.source_agent === 'agent-a' ? 'A' : memory.source_agent === 'agent-b' ? 'B' : 'M'}</span><span>{memory.source_agent}</span></div></td>
                    <td><div className="date-cell"><span>{relativeTime(memory.updated_at)}</span><small>{timeLabel(memory.updated_at, true)}</small></div></td>
                    <td><span className={`record-status record-${memory.status}`}><i />{memory.status}</span></td>
                    <td><div className="row-actions"><button className="icon-button" onClick={() => openEdit(memory)} title="Edit memory"><Edit3 size={15} /></button><button className="icon-button delete-action" onClick={() => remove(memory)} title="Delete memory"><Trash2 size={15} /></button></div></td>
                  </tr>
                  {memory.conflict_status === 'pending' && <tr className="conflict-row"><td colSpan="6"><div><AlertTriangle size={15} /><span>Possible conflict with <strong>{memory.conflict_with || 'another version'}</strong>. Both versions remain active until you decide.</span><button onClick={() => resolve(memory)} disabled={busyId === memory.id}><Check size={13} /> Make this current</button></div></td></tr>}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
        {!filtered.length && <EmptyState icon={Search} title="No matching memories" action={(query || category !== 'all' || status !== 'all') && <button className="button button-secondary" onClick={() => { setQuery(''); setCategory('all'); setStatus('all') }}>Clear filters</button>}>{memories.length ? 'Try changing your search or filters.' : 'Create a memory or share context with an agent to get started.'}</EmptyState>}
        <div className="vault-footer"><span><Clock3 size={13} /> Every record includes provenance and timestamps</span><span><FileJson size={13} /> JSON export includes all versions</span></div>
      </section>

      {modal && <Modal title={modal === 'create' ? 'Create a memory' : 'Edit memory'} description={modal === 'create' ? 'Add durable context directly to your local vault.' : `${modal.id} · created ${timeLabel(modal.created_at, true)}`} onClose={() => !saving && setModal(null)}>
        <form onSubmit={submit} className="memory-form">
          <label><span>Memory content <i>Required</i></span><textarea autoFocus required rows={5} value={form.content} onChange={(event) => setForm({ ...form, content: event.target.value })} placeholder="A durable goal, preference, decision, project detail, or commitment…" /></label>
          <div className="form-grid">
            <label><span>Category</span><select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{categories.map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label>
            <label><span>Status</span><select value={form.status} disabled={modal === 'create'} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="active">Active</option><option value="outdated">Outdated</option><option value="superseded">Superseded</option></select></label>
          </div>
          <label><span>Memory key <i>Optional · enables conflict detection</i></span><input value={form.memory_key} onChange={(event) => setForm({ ...form, memory_key: event.target.value })} placeholder="e.g. preferences.response_style" /></label>
          {modal === 'create' && <label><span>Source</span><input value={form.source_agent} onChange={(event) => setForm({ ...form, source_agent: event.target.value })} /></label>}
          <div className="form-note"><ShieldCheck size={16} /><span>Saving a different value with an existing key creates a flagged conflict instead of overwriting the original.</span></div>
          <div className="modal-actions"><button type="button" className="button button-secondary" onClick={() => setModal(null)} disabled={saving}>Cancel</button><button className="button button-primary" disabled={saving || !form.content.trim()}>{saving ? 'Saving…' : modal === 'create' ? 'Save to vault' : 'Save changes'}</button></div>
        </form>
      </Modal>}
    </div>
  )
}
