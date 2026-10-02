export type IllustrationKind = 'cow' | 'bag' | 'route' | 'empty'

/** Decorative: outcome and meaning must always be provided by adjacent text. */
export function Illustration({ kind }: { kind: IllustrationKind }) {
  return <img src={`/illustrations/${kind}.svg`} width="200" height="160" alt="" aria-hidden="true" style={{ maxWidth: '100%', objectFit: 'contain' }} />
}
