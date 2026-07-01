import { useState, KeyboardEvent } from 'react'

interface Props {
  value: string
  onSave: (val: string) => Promise<void>
  className?: string
  inputStyle?: React.CSSProperties
  placeholder?: string
  allowEmpty?: boolean
}

export default function InlineEdit({ value, onSave, className, inputStyle, placeholder, allowEmpty }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [busy, setBusy] = useState(false)

  function startEdit() {
    setDraft(value)
    setEditing(true)
  }

  async function save() {
    if (!allowEmpty && draft.trim() === '') { setEditing(false); return }
    if (draft === value) { setEditing(false); return }
    setBusy(true)
    try {
      await onSave(draft.trim())
      setEditing(false)
    } catch {
      // keep editing open on error
    } finally {
      setBusy(false)
    }
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') save()
    if (e.key === 'Escape') setEditing(false)
  }

  if (editing) {
    return (
      <span className="inline-edit-active">
        <input
          autoFocus
          value={draft}
          placeholder={placeholder}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={onKey}
          className="inline-edit-input"
          style={inputStyle}
          disabled={busy}
        />
        <button className="btn-ghost btn-xs" onClick={save} disabled={busy} title="Save (Enter)">✓</button>
        <button className="btn-ghost btn-xs" onClick={() => setEditing(false)} title="Cancel (Esc)">✕</button>
      </span>
    )
  }

  return (
    <span className={`inline-edit-view ${className ?? ''}`}>
      {value || <span className="muted">{placeholder ?? '—'}</span>}
      <button className="btn-ghost btn-xs inline-edit-pencil" onClick={startEdit} title="Edit">✎</button>
    </span>
  )
}
