export function Logo({ compact = false }: { compact?: boolean }) {
  return <span className="row" aria-label="SITRAP">
    <img src="/brand/sitrap-symbol.svg" width={compact ? 32 : 48} height={compact ? 32 : 48} alt="" />
    {!compact && <strong className="text-xl tracking-wider">SITRAP</strong>}
  </span>
}
