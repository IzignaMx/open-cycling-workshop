import type {
  CaptureCheckpoint,
  CaptureDraftContent,
} from '../../src/access-kernel/capture-checkpoint-types.js'
import type { OwnedOperation } from '../../src/access-kernel/types.js'
export const witnessId: string
export function captureFixture(
  now: number,
  ttl: number,
  canonicalJson: (value: unknown) => string,
): {
  checkpoint: CaptureCheckpoint
  customer: CaptureDraftContent
  future: Record<string, unknown>
  witness: CaptureDraftContent
  journal: OwnedOperation
}
