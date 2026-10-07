export function Logo({ compact = false }: { compact?: boolean }) {
  return <img src={compact ? '/brand/sitrap-icon.svg' : '/brand/sitrap-logo.svg'}
    width={compact ? 40 : 170} height={compact ? 40 : 70} alt="SITRAP" />
}
