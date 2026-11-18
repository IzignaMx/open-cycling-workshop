export interface CustodyArtifactProvenance {
  currentHead: string
  currentTree: string
  source: Record<string, string>
  lockSha256: string
  scope: string
  assets: Record<string, { bytes: number; sha256: string }>
}
export function expectedProvenance(): Promise<CustodyArtifactProvenance>
export function verifyArtifactProvenance(actual: unknown, expected: CustodyArtifactProvenance): void
export function build(): Promise<CustodyArtifactProvenance>
