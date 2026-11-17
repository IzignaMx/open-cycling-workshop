/** Synthetic adapters only. Staging never confers exclusive ownership or permission to submit. */
export async function stageObservedDraft({ snapshot, stage, recheck }) {
  const source = await snapshot()
  if (source.kind !== 'snapshot') return source
  const staged = await stage(source.bundle)
  if (!['staged', 'already_staged'].includes(staged.kind)) return staged
  let observation = 'unavailable'
  try {
    const result = await recheck(source.witness)
    if (['source_changed', 'source_unchanged_at_check'].includes(result.kind))
      observation = result.kind
  } catch {
    /* An uncertain recheck never deletes verified custody or grants authority. */
  }
  return { kind: 'custody_retained', observation, operationalUse: 'forbidden' }
}
