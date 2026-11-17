import React from 'react'
import { AlertTriangle, Check, CheckCircle2, Info, X } from 'lucide-react'

export function StatusDot({ status = 'standby', pulse = false }) {
  return <span className={`status-dot status-${status} ${pulse ? 'pulse' : ''}`} aria-hidden="true" />
}

export function StatusBadge({ status, children, className = '' }) {
  return (
    <span className={`status-badge status-badge-${status} ${className}`}>
      <StatusDot status={status} />
      {children}
    </span>
  )
}

export function CategoryBadge({ children }) {
  return <span className={`category-badge category-${String(children).toLowerCase()}`}>{children}</span>
}

export function SectionHeading({ eyebrow, title, description, action }) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="section-actions">{action}</div>}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="empty-state">
      {Icon && <div className="empty-icon"><Icon size={22} strokeWidth={1.6} /></div>}
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function Toast({ toast, onClose }) {
  if (!toast) return null
  const Icon = toast.tone === 'error' ? AlertTriangle : toast.tone === 'info' ? Info : CheckCircle2
  return (
    <div className={`toast toast-${toast.tone || 'success'}`} role="status">
      <Icon size={18} />
      <span>{toast.message}</span>
      <button className="icon-button" onClick={onClose} aria-label="Dismiss notification"><X size={16} /></button>
    </div>
  )
}

export function StepState({ status }) {
  if (status === 'failed' || status === 'offline') return <span className={`trace-state trace-${status}`}>{status === 'offline' ? '—' : '!'}</span>
  if (status === 'skipped') return <span className="trace-state trace-skipped">—</span>
  return <span className="trace-state trace-complete"><Check size={12} strokeWidth={2.5} /></span>
}

export function Modal({ title, description, onClose, children }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-header">
          <div><h3>{title}</h3>{description && <p>{description}</p>}</div>
          <button className="icon-button" onClick={onClose} aria-label="Close"><X size={19} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}
