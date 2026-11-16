import type { components } from './generated'
import type { components as Backend } from './backend.generated'
import type { CuyType } from '../cuyes/types'
import type { SaleType } from '../cuyes/salesTypes'
export type Role = Backend['schemas']['RoleEnum']
export type Assignment = Omit<components['schemas']['Assignment'], 'role'> & { role: Role }
export type Account = Omit<components['schemas']['Account'], 'assignments'> & { assignments: Assignment[] }
export type ErrorBody = components['schemas']['ErrorBody']
export type CommandType = components['schemas']['CommandType'] | CuyType | SaleType
export type Command = Omit<components['schemas']['Command'], 'type'> & { type: CommandType }
export type Acknowledgement = components['schemas']['Acknowledgement']
export interface Page<T> { results: T[]; next: string | null; count: number }
