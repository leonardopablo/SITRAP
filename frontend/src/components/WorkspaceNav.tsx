import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { navigation } from '../auth/workspace'
import type { Role } from '../api/types'
import { NavIcon } from './NavIcon'

export function WorkspaceNav({ role }: { role: Role }) {
  const scroller = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ left: false, right: false })

  useEffect(() => {
    const element = scroller.current
    if (!element) return
    const update = () => {
      const left = element.scrollLeft > 2
      const right = element.scrollWidth - element.clientWidth - element.scrollLeft > 2
      setEdges(previous => previous.left === left && previous.right === right ? previous : { left, right })
    }
    update()
    element.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update)
    observer?.observe(element)
    for (const link of element.children) observer?.observe(link)
    return () => {
      element.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
      observer?.disconnect()
    }
  }, [role])

  useLayoutEffect(() => {
    const element = scroller.current
    if (!element || !window.matchMedia?.('(max-width: 47.999rem)').matches) return
    const active = element.querySelector<HTMLElement>('[aria-current="page"]')
    if (active) element.scrollLeft = active.offsetLeft - element.offsetLeft
  }, [role])

  return <nav className="workspace-nav" aria-label="Navegación principal">
    <div className={`workspace-nav__scroller${edges.left ? ' has-more-left' : ''}${edges.right ? ' has-more-right' : ''}`} ref={scroller}>
      {navigation[role].map(item => <NavLink key={item.to} to={item.to} end><NavIcon name={item.icon} /><span>{item.label}</span></NavLink>)}
    </div>
  </nav>
}
