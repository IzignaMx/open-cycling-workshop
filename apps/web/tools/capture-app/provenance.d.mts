export interface Evidence {
  source_commit: string
  source_tree: string
  lock_sha256: string
  database: string
  assets: Record<string, { bytes: number; sha256: string }>
}
export const oldCommit: string
export function hash(bytes: Uint8Array | string): string
export function expectedEvidence(kind: 'old' | 'current'): Evidence
export function validateEvidence(
  actual: Evidence,
  expected: Omit<Evidence, 'assets'>,
  readAsset: (path: string) => Uint8Array,
): Evidence

export function validateStartupBarrier(controller: string, app: string): void
