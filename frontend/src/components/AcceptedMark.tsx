/** Render only after an individual server acknowledgement, never for a local outbox write. */
export function AcceptedMark({ label }: { label: string }) {
  return <span className="accepted-mark" role="status"><span className="accepted-mark__symbol" aria-hidden="true">✓</span>{label}</span>
}
