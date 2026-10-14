import { BookOpen, CircleHelp, Clock3, History, House, LayoutDashboard, Milk, PackageCheck, Route, Tag, Truck, UsersRound, type LucideIcon } from 'lucide-react'
import type { NavIconName } from '../auth/workspace'

const icons: Record<NavIconName, LucideIcon> = {
  home: House,
  production: Milk,
  cows: Tag,
  history: History,
  transport: Truck,
  pending: Clock3,
  reception: PackageCheck,
  admin: LayoutDashboard,
  trace: Route,
  users: UsersRound,
  catalog: BookOpen,
  help: CircleHelp,
}

export function NavIcon({ name }: { name: NavIconName }) {
  const Icon = icons[name]
  return <Icon className="workspace-nav__icon" size={24} strokeWidth={2} aria-hidden="true" focusable="false" />
}
