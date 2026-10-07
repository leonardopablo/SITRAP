export function Logo({ compact = false }: { compact?: boolean }) {
  return <img src={compact ? '/brand/sitrap-icon.svg' : '/brand/sitrap-logo.svg'}
    width={compact ? 40 : 210} height={compact ? 40 : 86} alt="SITRAP" />
}
