import type { KernelDatabase } from './database.js'
import type {
  CaptureCheckpoint,
  CaptureCheckpointCommand,
  CaptureCheckpointResult,
  CaptureDraftContent,
  Channel,
  CleanupResult,
  ContentProjection,
} from './capture-checkpoint-types.js'
import {
  CAPTURE_TTL_MS,
  MAX_CONTENT_UTF8_BYTES,
  MAINTENANCE_PAGE_SIZE,
  emptyChannel,
  writerEpoch,
  newCaptureWriter,
  frozenCopy,
  projectionBytes,
  validCheckpoint,
  validCommandShape,
  validContent,
  preservableUnsupportedContent,
  validHash,
  validInteger,
  validProjection,
  validUUID,
} from './capture-checkpoint.js'
const channels: Channel[] = ['customer', 'order']
const refused = (
  reason: Exclude<
    Extract<CaptureCheckpointResult, { kind: 'refused' }>['reason'],
    'unsupported_format'
  >,
): CaptureCheckpointResult => ({ kind: 'refused', reason })
const unsupported = (checkpoint: CaptureCheckpoint): CaptureCheckpointResult =>
  frozenCopy({ kind: 'refused', reason: 'unsupported_format', checkpoint })
const keys = (id: string): [string, string][] => channels.map((channel) => [id, channel])
function matches(
  row: CaptureDraftContent,
  checkpoint: CaptureCheckpoint,
  channel: Channel,
): boolean {
  const state = checkpoint[channel]
  return (
    row.checkpointId === checkpoint.checkpointId &&
    row.channel === channel &&
    row.generation === checkpoint.generation &&
    row.revision === state.revision &&
    row.firstPersistedAt === state.contentStartedAt &&
    row.expiresAt === state.contentExpiresAt
  )
}
/** Row reducer only. Caller MUST include these stores in its already admitted kernel transaction. */
export async function applyCaptureCheckpoint(
  db: KernelDatabase,
  command: CaptureCheckpointCommand,
  bindingKey: string,
  scopeKey: string,
  now: number,
): Promise<CaptureCheckpointResult> {
  if (
    !validCommandShape(command) ||
    !validInteger(now) ||
    !validUUID(command.checkpointId) ||
    !validHash(bindingKey) ||
    !validHash(scopeKey)
  )
    return refused('invalid')
  const stored = await db.captureCheckpoints.get(command.checkpointId)
  if (command.kind === 'enroll') {
    if (!validUUID(command.generation)) return refused('invalid')
    if (stored || (await db.captureCheckpoints.where('bindingKey').equals(bindingKey).first()))
      return refused('conflict')
    const control = await db.deviceControl.get('device')
    if (!control || !validInteger(control.localSequence)) return refused('unavailable')
    const epoch = writerEpoch(control) ?? crypto.randomUUID()
    control.captureWriter = newCaptureWriter(control, epoch)
    await db.deviceControl.put(control)
    const checkpoint: CaptureCheckpoint = {
      writerEpoch: epoch,
      format: 1,
      checkpointId: command.checkpointId,
      bindingKey,
      scopeKey,
      generation: command.generation,
      closed: false,
      observedAt: now,
      customer: emptyChannel(),
      order: emptyChannel(),
    }
    await db.captureCheckpoints.add(checkpoint)
    return frozenCopy({ kind: 'ack', checkpoint })
  }
  if (!stored) return refused('missing')
  if (!validCheckpoint(stored)) return refused('invalid')
  const checkpoint = stored
  const control = await db.deviceControl.get('device')
  if (!control || writerEpoch(control) !== checkpoint.writerEpoch) return refused('unavailable')
  if (checkpoint.bindingKey !== bindingKey) return refused('conflict')
  if (checkpoint.closed) return refused('closed')
  if (now < checkpoint.observedAt) return refused('clock')
  if (command.kind === 'load' && checkpoint.scopeKey !== scopeKey)
    return frozenCopy({ kind: 'scope_changed', checkpoint })
  if (command.kind !== 'retireScope' && checkpoint.scopeKey !== scopeKey) return refused('conflict')
  if (
    command.kind !== 'load' &&
    (!validUUID(command.generation) || checkpoint.generation !== command.generation)
  )
    return refused('conflict')
  if (command.kind === 'load') {
    const contents: Partial<Record<Channel, CaptureDraftContent>> = {}
    for (const channel of channels) {
      const state = checkpoint[channel]
      if (state.state !== 'UNSENT') continue
      const row = await db.captureDraftContents.get([checkpoint.checkpointId, channel])
      if (row && preservableUnsupportedContent(row) && matches(row, checkpoint, channel))
        return unsupported(checkpoint)
      if (!validContent(row) || !matches(row, checkpoint, channel)) return refused('invalid')
      if (now < row.firstPersistedAt) return refused('clock')
      if (now >= row.expiresAt) return refused('expired')
      contents[channel] = row
    }
    checkpoint.observedAt = now
    await db.captureCheckpoints.put(checkpoint)
    return frozenCopy({ kind: 'loaded', checkpoint, contents })
  }
  if (command.kind === 'retireScope') {
    if (
      !validUUID(command.nextGeneration) ||
      command.nextGeneration === checkpoint.generation ||
      scopeKey === checkpoint.scopeKey
    )
      return refused('invalid')
    if (channels.some((channel) => !validInteger(checkpoint[channel].revision + 1)))
      return refused('invalid')
    checkpoint.generation = command.nextGeneration
    checkpoint.scopeKey = scopeKey
    for (const channel of channels) {
      const state = checkpoint[channel]
      checkpoint[channel] =
        state.state === 'PROTECTED' || state.state === 'UNAVAILABLE'
          ? {
              ...state,
              revision: state.revision + 1,
              contentStartedAt: null,
              contentExpiresAt: null,
            }
          : emptyChannel(state.revision + 1)
    }
    await db.captureDraftContents.bulkDelete(keys(checkpoint.checkpointId))
  } else {
    if (!channels.includes(command.channel) || !validInteger(command.expectedRevision))
      return refused('invalid')
    const state = checkpoint[command.channel]
    if (state.revision !== command.expectedRevision) return refused('conflict')
    if (!validInteger(state.revision + 1)) return refused('invalid')
    if (state.state === 'UNAVAILABLE') return refused('protected')
    if (state.state === 'UNSENT') {
      const row = await db.captureDraftContents.get([checkpoint.checkpointId, command.channel])
      if (row && preservableUnsupportedContent(row) && matches(row, checkpoint, command.channel))
        return unsupported(checkpoint)
      if (!validContent(row) || !matches(row, checkpoint, command.channel))
        return refused('invalid')
    }
    let content: ContentProjection | null = null
    if (command.kind === 'settle') {
      if (
        state.state !== 'PROTECTED' ||
        !validUUID(command.attemptId) ||
        state.attemptId !== command.attemptId
      )
        return refused('conflict')
      if (command.outcome !== 'saved' && command.outcome !== 'not_saved') return refused('invalid')
      content = command.content
    } else {
      if (state.state === 'PROTECTED') return refused('protected')
      if (command.kind === 'save') content = command.content
      else if (command.kind !== 'protect') return refused('invalid')
    }
    if (content !== null && (!validProjection(content) || content.channel !== command.channel))
      return refused('invalid')
    if (content !== null && projectionBytes(content) > MAX_CONTENT_UTF8_BYTES)
      return refused('oversize')
    if (command.kind === 'protect') {
      if (!validUUID(command.attemptId)) return refused('invalid')
      if (state.contentExpiresAt !== null && now >= state.contentExpiresAt)
        return refused('expired')
      checkpoint[command.channel] = {
        ...state,
        revision: state.revision + 1,
        state: 'PROTECTED',
        attemptId: command.attemptId,
      }
      await db.captureDraftContents.delete([checkpoint.checkpointId, command.channel])
    } else {
      const expired = state.contentExpiresAt !== null && now >= state.contentExpiresAt
      if (expired && command.kind === 'save') return refused('expired')
      if (content === null || expired) {
        checkpoint[command.channel] = emptyChannel(state.revision + 1)
        await db.captureDraftContents.delete([checkpoint.checkpointId, command.channel])
      } else {
        const first = state.contentStartedAt ?? now,
          expires = state.contentExpiresAt ?? first + CAPTURE_TTL_MS
        if (!validInteger(expires)) return refused('invalid')
        checkpoint[command.channel] = {
          revision: state.revision + 1,
          state: 'UNSENT',
          attemptId: null,
          contentStartedAt: first,
          contentExpiresAt: expires,
        }
        await db.captureDraftContents.put({
          ...content,
          format: 1,
          checkpointId: checkpoint.checkpointId,
          generation: checkpoint.generation,
          revision: state.revision + 1,
          firstPersistedAt: first,
          expiresAt: expires,
        })
      }
    }
  }
  checkpoint.observedAt = now
  await db.captureCheckpoints.put(checkpoint)
  return frozenCopy({ kind: 'ack', checkpoint })
}
/** Delete private content only; an old logout callback must not close a replacement. */
export async function purgeCaptureContents(
  db: KernelDatabase,
  checkpointId: string,
  generation: string,
): Promise<CleanupResult> {
  if (!validUUID(checkpointId) || !validUUID(generation)) return { kind: 'unavailable' }
  try {
    await db.transaction('rw', [db.captureCheckpoints, db.captureDraftContents], async () => {
      const checkpoint = await db.captureCheckpoints.get(checkpointId)
      if (!checkpoint) {
        for (const channel of channels) {
          const row = await db.captureDraftContents.get([checkpointId, channel])
          if (row?.generation === generation)
            await db.captureDraftContents.delete([checkpointId, channel])
        }
        return
      }
      if (checkpoint.generation !== generation) return
      if (!validCheckpoint(checkpoint)) throw new Error('Invalid checkpoint')
      checkpoint.closed = true
      for (const channel of channels) {
        const state = checkpoint[channel]
        if (!validInteger(state.revision + 1)) throw new Error('Revision overflow')
        checkpoint[channel] =
          state.state === 'PROTECTED' || state.state === 'UNAVAILABLE'
            ? {
                ...state,
                revision: state.revision + 1,
                contentStartedAt: null,
                contentExpiresAt: null,
              }
            : emptyChannel(state.revision + 1)
      }
      await db.captureDraftContents.bulkDelete(keys(checkpointId))
      await db.captureCheckpoints.put(checkpoint)
    })
    return { kind: 'complete' }
  } catch {
    return { kind: 'unavailable' }
  }
}
/** Bounded all-key scan includes malformed rows omitted from the expiry index. */
export async function sweepExpiredCaptureContents(
  db: KernelDatabase,
  now: number,
): Promise<CleanupResult> {
  if (!validInteger(now)) return { kind: 'unavailable' }
  try {
    let after: [string, string] | undefined
    let unresolvedClock = false
    for (;;) {
      const page = await db.transaction(
        'rw',
        [db.captureCheckpoints, db.captureDraftContents],
        async () => {
          const query = after
            ? db.captureDraftContents.where(':id').above(after)
            : db.captureDraftContents.toCollection()
          const rows = await query.limit(MAINTENANCE_PAGE_SIZE).toArray()
          for (const row of rows) {
            const checkpoint = await db.captureCheckpoints.get(row.checkpointId)
            const channel = row.channel
            const usable = validCheckpoint(checkpoint) && channels.includes(channel)
            const unsupported = preservableUnsupportedContent(row)
            const wellFormed =
              (validContent(row) || unsupported) && usable && matches(row, checkpoint, channel)
            const rollback = usable && now < checkpoint.observedAt
            if (
              unsupported &&
              wellFormed &&
              !checkpoint.closed &&
              checkpoint[channel].state === 'UNSENT' &&
              (rollback || now < row.firstPersistedAt)
            ) {
              unresolvedClock = true
              continue
            }
            if (
              wellFormed &&
              !rollback &&
              now >= row.firstPersistedAt &&
              now < row.expiresAt &&
              !checkpoint.closed &&
              checkpoint[channel].state === 'UNSENT'
            )
              continue
            await db.captureDraftContents.delete([row.checkpointId, channel])
            if (
              usable &&
              checkpoint[channel].state !== 'PROTECTED' &&
              checkpoint[channel].state !== 'UNAVAILABLE'
            ) {
              const revision = checkpoint[channel].revision + 1
              if (!validInteger(revision)) throw new Error('Revision overflow')
              checkpoint[channel] =
                wellFormed && !rollback && now >= row.expiresAt
                  ? emptyChannel(revision)
                  : { ...emptyChannel(revision), state: 'UNAVAILABLE' }
              checkpoint.observedAt = Math.max(checkpoint.observedAt, now)
              await db.captureCheckpoints.put(checkpoint)
            }
          }
          return {
            count: rows.length,
            last: rows.length
              ? ([rows[rows.length - 1]!.checkpointId, rows[rows.length - 1]!.channel] as [
                  string,
                  string,
                ])
              : undefined,
          }
        },
      )
      if (page.count < MAINTENANCE_PAGE_SIZE)
        return { kind: unresolvedClock ? 'unavailable' : 'complete' }
      after = page.last
    }
  } catch {
    return { kind: 'unavailable' }
  }
}

/** Explicit discard is deletion-only: fence callbacks without changing scope or granting admission. */
export async function retireCaptureContents(
  db: KernelDatabase,
  checkpointId: string,
  generation: string,
  nextGeneration: string,
): Promise<{ kind: 'retired'; checkpoint: CaptureCheckpoint } | { kind: 'unavailable' }> {
  if (
    !validUUID(checkpointId) ||
    !validUUID(generation) ||
    !validUUID(nextGeneration) ||
    generation === nextGeneration
  )
    return { kind: 'unavailable' }
  try {
    return await db.transaction(
      'rw',
      [db.captureCheckpoints, db.captureDraftContents],
      async () => {
        const checkpoint = await db.captureCheckpoints.get(checkpointId)
        if (!validCheckpoint(checkpoint) || checkpoint.generation !== generation)
          return { kind: 'unavailable' } as const
        if (channels.some((channel) => !validInteger(checkpoint[channel].revision + 1)))
          return { kind: 'unavailable' } as const
        checkpoint.generation = nextGeneration
        for (const channel of channels) {
          const state = checkpoint[channel]
          checkpoint[channel] =
            state.state === 'PROTECTED' || state.state === 'UNAVAILABLE'
              ? {
                  ...state,
                  revision: state.revision + 1,
                  contentStartedAt: null,
                  contentExpiresAt: null,
                }
              : emptyChannel(state.revision + 1)
        }
        await db.captureDraftContents.bulkDelete(keys(checkpointId))
        await db.captureCheckpoints.put(checkpoint)
        return frozenCopy({ kind: 'retired' as const, checkpoint })
      },
    )
  } catch {
    return { kind: 'unavailable' }
  }
}
