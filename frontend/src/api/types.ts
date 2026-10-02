import type { components } from './generated'
export type Role = components['schemas']['Role']
export type Assignment = components['schemas']['Assignment']
export type Account = components['schemas']['Account']
export type ErrorBody = components['schemas']['ErrorBody']
export type CommandType = components['schemas']['CommandType']
export type Command = components['schemas']['Command']
export type Acknowledgement = components['schemas']['Acknowledgement']
export interface Page<T> { results: T[]; next: string | null; count: number }
