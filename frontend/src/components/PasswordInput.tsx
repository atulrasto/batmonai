import { useState } from 'react'

interface Props {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  required?: boolean
  autoFocus?: boolean
  minLength?: number
  id?: string
}

export default function PasswordInput({ value, onChange, placeholder, required, autoFocus, minLength, id }: Props) {
  const [show, setShow] = useState(false)
  return (
    <div className="pw-wrap">
      <input
        id={id}
        type={show ? 'text' : 'password'}
        value={value}
        required={required}
        autoFocus={autoFocus}
        minLength={minLength}
        placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        className="pw-input"
      />
      <button
        type="button"
        className="pw-toggle"
        onClick={() => setShow(s => !s)}
        aria-label={show ? 'Hide password' : 'Show password'}
        tabIndex={-1}
      >
        {show ? '🙈' : '👁️'}
      </button>
    </div>
  )
}
