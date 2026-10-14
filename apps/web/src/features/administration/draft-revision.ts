/** A receipt belongs to one dispatched draft, never to later edits or a global status. */
export function isConfirmedDraftRevision(
  receipt: unknown,
  submittedRevision: number,
  currentRevision: number,
): boolean {
  return receipt === 'confirmed' && submittedRevision === currentRevision
}
