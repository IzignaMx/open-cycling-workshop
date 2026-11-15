import type { BrowserContext } from '@playwright/test'
export interface ProcessIdentity {
  pid: number
  starttime: string
}
export interface Termination {
  pagesClosed: true
  browserDisconnected: true
  procAbsent: true
}
export interface RestartIdentity {
  first: ProcessIdentity
  second: ProcessIdentity
  profileSha256: string
  firstTermination: Termination
}
export function runRestart<T>(options: {
  launch: (
    profile: string,
    options: { offline: boolean; serviceWorkers: 'allow' },
  ) => Promise<BrowserContext>
  first: (context: BrowserContext, identity: ProcessIdentity) => Promise<T>
  second: (context: BrowserContext, before: T, identities: RestartIdentity) => Promise<void>
  finish: (context: BrowserContext, phase: number) => Promise<void>
}): Promise<RestartIdentity & { secondTermination: Termination }>
