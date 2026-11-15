import { captureFixture } from './fixture.mjs'
export const protectedId = '55555555-5555-4555-8555-555555555555'
export function crashFixture(now, ttl, canonicalJson) {
  const seeded = captureFixture(now, ttl, canonicalJson)
  return {
    ...seeded,
    protectedCheckpoint: {
      ...seeded.checkpoint,
      checkpointId: protectedId,
      bindingKey: 'c'.repeat(64),
      customer: {
        revision: 0,
        state: 'EMPTY',
        attemptId: null,
        contentStartedAt: null,
        contentExpiresAt: null,
      },
      order: {
        ...seeded.checkpoint.order,
        state: 'PROTECTED',
        attemptId: '66666666-6666-4666-8666-666666666666',
      },
    },
  }
}
// Node-only fixture admission. PROTECTED is a separate safety state, not a
// synonym for the original UNSENT future row. Its payload must be absent.
export function validCrashFixture(data, validCheckpoint) {
  const protectedCheckpoint = data.protectedCheckpoint
  return (
    validCheckpoint(data.checkpoint) &&
    validCheckpoint(protectedCheckpoint) &&
    protectedCheckpoint.checkpointId === protectedId &&
    protectedCheckpoint.checkpointId !== data.checkpoint.checkpointId &&
    protectedCheckpoint.order.state === 'PROTECTED' &&
    protectedCheckpoint.customer.state === 'EMPTY' &&
    data.checkpoint.customer.state === 'UNSENT' &&
    data.checkpoint.order.state === 'UNSENT' &&
    [data.customer, data.future, data.witness].every((row) => row.checkpointId !== protectedId)
  )
}
