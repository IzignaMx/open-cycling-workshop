import type {
  CustomerDraftState,
  OrderDraftState,
  RetainedOrderSelection,
} from '../features/draft-state.js'
import type { CaptureVisitScope } from '../runtime/capture-visit.js'
export type Channel = 'customer' | 'order'
export interface ChannelCheckpoint {
  revision: number
  state: 'EMPTY' | 'UNSENT' | 'PROTECTED' | 'UNAVAILABLE'
  attemptId: string | null
  contentStartedAt: number | null
  contentExpiresAt: number | null
}
export interface CaptureCheckpoint {
  writerEpoch: string
  format: 1
  checkpointId: string
  bindingKey: string
  scopeKey: string
  generation: string
  closed: boolean
  observedAt: number
  customer: ChannelCheckpoint
  order: ChannelCheckpoint
}
export type ContentProjection =
  | { channel: 'customer'; draft: CustomerDraftState }
  | { channel: 'order'; draft: OrderDraftState; retainedSelection: RetainedOrderSelection }
export type CaptureDraftContent = ContentProjection & {
  format: 1
  checkpointId: string
  generation: string
  revision: number
  firstPersistedAt: number
  expiresAt: number
}
type Identity = { checkpointId: string; scope: CaptureVisitScope }
type Expected = Identity & { generation: string }
type ChannelCAS = Expected & { channel: Channel; expectedRevision: number }
export type CaptureCheckpointCommand =
  | (Identity & { kind: 'enroll'; generation: string })
  | (Identity & { kind: 'load' })
  | (ChannelCAS & { kind: 'save'; content: ContentProjection })
  | (ChannelCAS & { kind: 'protect'; attemptId: string })
  | (ChannelCAS & {
      kind: 'settle'
      attemptId: string
      outcome: 'saved' | 'not_saved'
      content: ContentProjection | null
    })
  | (Expected & { kind: 'retireScope'; nextGeneration: string })
export type CaptureCheckpointResult =
  | { kind: 'ack'; checkpoint: CaptureCheckpoint }
  | { kind: 'scope_changed'; checkpoint: CaptureCheckpoint }
  | {
      kind: 'loaded'
      checkpoint: CaptureCheckpoint
      contents: Partial<Record<Channel, CaptureDraftContent>>
    }
  | { kind: 'refused'; reason: 'unsupported_format'; checkpoint: CaptureCheckpoint }
  | {
      kind: 'refused'
      reason:
        | 'missing'
        | 'conflict'
        | 'closed'
        | 'protected'
        | 'expired'
        | 'invalid'
        | 'clock'
        | 'oversize'
        | 'unavailable'
    }
export type CleanupResult = { kind: 'complete' } | { kind: 'unavailable' }
