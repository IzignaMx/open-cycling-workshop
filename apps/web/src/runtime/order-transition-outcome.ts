/** Local commit evidence, never a server acknowledgement or rollback proof. */
export type OrderTransitionResult =
  { status: 'committed'; view: 'updated' | 'unavailable' } | { status: 'unknown' }
