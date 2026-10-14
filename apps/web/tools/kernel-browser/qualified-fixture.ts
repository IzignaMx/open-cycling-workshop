import { contextKey } from '../../src/access-kernel/context.js'
import { canonicalJson } from '../../src/access-kernel/operations.js'
import type { BaselineMetadata } from '../../src/access-kernel/baseline-state.js'
import type { ContextTicket, VerifiedAccessContext } from '../../src/access-kernel/types.js'

/** Synthetic supported-protocol proof for existing kernel tests, never a server advertisement. */
export function completedMetadata(
  ticket: ContextTicket,
  context: VerifiedAccessContext,
  checkpoint: string,
): BaselineMetadata {
  if (context.snapshotProtocol !== 'baseline-v1')
    throw new Error('Synthetic qualified fixture only')
  const baselineId = '00000000-0000-0000-0000-000000000001'
  const expiresAt = new Date(
    Math.min(Date.parse(context.offlineUntil), Date.parse(context.verifiedAt) + 1800000),
  ).toISOString()
  const requestId = '00000000-0000-0000-0000-000000000002'
  const wireContext = {
    protocol: 1,
    principal: {
      api_realm: null,
      organization_id: context.principal.organizationId,
      user_id: context.principal.userId,
    },
    account_location_id: context.accountLocationId,
    selected_location_id: context.selectedLocationId,
    capabilities: [...context.capabilities],
    authorization_epoch: context.authorizationEpoch,
    policy_revision: context.policyRevision,
    verified_at: context.verifiedAt,
    offline_until: context.offlineUntil,
    snapshot_protocol: context.snapshotProtocol,
  }
  return {
    format: 1,
    binding: contextKey(context),
    origin: ticket,
    owner: ticket,
    requestId,
    startBody: canonicalJson({
      protocol: 1,
      selected_location_id: context.selectedLocationId,
      authorization_epoch: context.authorizationEpoch,
      request_id: requestId,
    }),
    startResponse: canonicalJson({
      protocol: 1,
      baseline_id: baselineId,
      context: wireContext,
      continuation: 'scan-0',
      expires_at: expiresAt,
    }),
    baselineId,
    expiresAt,
    phase: 'active',
    next: null,
    checkpoint,
    receipt: {
      kind: 'delta',
      predecessor: 'delta-0',
      response: canonicalJson({
        protocol: 1,
        baseline_id: baselineId,
        authorization_epoch: context.authorizationEpoch,
        page_id: 'page',
        predecessor: 'delta-0',
        records: [],
        phase: 'complete',
        continuation: checkpoint,
        completion: {
          baseline_id: baselineId,
          authorization_epoch: context.authorizationEpoch,
          checkpoint,
        },
      }),
    },
    retryCount: 0,
    hold: null,
  }
}
