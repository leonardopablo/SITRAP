import { useEffect, useId, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'

export function Button({ busy, variant = 'primary', children, disabled, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean; variant?: 'primary' | 'secondary' | 'danger' }) {
  return <button {...props} className={`button ${variant}`} disabled={disabled || busy} aria-busy={busy || undefined}>{children}</button>
}

export function Field({ label, error, help, id, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; help?: string }) {
  const generated = useId()
  const fieldId = id ?? generated
  return <div className="field">
    <label htmlFor={fieldId}>{label}</label>
    <input {...props} id={fieldId} aria-invalid={!!error} aria-describedby={error ? `${fieldId}-error` : help ? `${fieldId}-help` : undefined} />
    {help && <span id={`${fieldId}-help`} className="help">{help}</span>}
    {error && <span id={`${fieldId}-error`} className="error">{error}</span>}
  </div>
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warning' | 'error' | 'success' }) {
  return <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{children}</div>
}

export function Dialog({ open, title, children, onClose }: { open: boolean; title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    if (!open) { ref.current?.close(); return }
    const previous = document.activeElement as HTMLElement | null
    ref.current?.showModal()
    return () => { ref.current?.close(); previous?.focus() }
  }, [open])
  return <dialog ref={ref} aria-labelledby={id} onCancel={onClose}>
    <h2 id={id}>{title}</h2>{children}<Button variant="secondary" onClick={onClose}>Cerrar</Button>
  </dialog>
}
