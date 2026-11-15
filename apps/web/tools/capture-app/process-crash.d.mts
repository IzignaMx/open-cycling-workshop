import type { BrowserContext } from '@playwright/test'
export interface ProcessMetadata {
  pid: number
  starttime: string
  pgrp: number
  session: number
}
export interface CrashProcessIdentity extends ProcessMetadata {
  cmdline: string
  known: ProcessMetadata[]
}
export interface CrashTermination {
  pagesClosed: true
  browserDisconnected: true
  procAbsent: true
  groupAbsent: true
  sessionAbsent: true
}
export interface CrashReceipt extends CrashTermination {
  method: 'Browser.crash'
  commandOutcome: 'resolved' | 'transport-closed' | 'unacknowledged-terminated'
}
export interface CrashRecoveryIdentity {
  first: CrashProcessIdentity
  second: CrashProcessIdentity
  profileSha256: string
  firstTermination: CrashTermination
  crashReceipt: CrashReceipt
}
export interface CrashLifecycleEvent {
  readonly stage: 'identified' | 'dispatch-begin' | 'command-outcome' | 'absence' | 'failure'
  readonly phase: number
  readonly profileSha256: string
  readonly identity?: Readonly<ProcessMetadata> & {
    readonly known: readonly Readonly<ProcessMetadata>[]
  }
  readonly crashAttempt?: Readonly<{
    method: 'Browser.crash'
    dispatched: true
    commandOutcome:
      'pending' | 'resolved' | 'transport-closed' | 'unacknowledged-terminated' | 'failed'
    terminationVerified: boolean
  }>
}
export function runCrashRecovery<T>(options: {
  launch: (
    profile: string,
    options: { offline: boolean; serviceWorkers: 'allow' },
  ) => Promise<BrowserContext>
  first: (context: BrowserContext, identity: CrashProcessIdentity) => Promise<T>
  second: (context: BrowserContext, before: T, identities: CrashRecoveryIdentity) => Promise<void>
  finish: (context: BrowserContext, phase: number) => Promise<void>
  onEvent?: (event: CrashLifecycleEvent) => void
}): Promise<CrashRecoveryIdentity & { secondTermination: CrashTermination }>
