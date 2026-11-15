import type { CaptureCheckpoint } from '../../src/access-kernel/capture-checkpoint-types.js'
import type { captureFixture } from './fixture.mjs'
export const protectedId: string
export type CrashFixture = ReturnType<typeof captureFixture> & {
  protectedCheckpoint: CaptureCheckpoint
}
export function crashFixture(
  now: number,
  ttl: number,
  canonicalJson: (value: unknown) => string,
): CrashFixture
export function validCrashFixture(
  data: CrashFixture,
  validCheckpoint: (value: unknown) => boolean,
): boolean
