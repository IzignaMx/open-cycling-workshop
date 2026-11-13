export const pin: string
interface Provenance {
  historical: { commit: string; dexie: string; files: Record<string, string> }
  currentHead: string
  source: Record<string, string>
  scope: string
}
export function expectedProvenance(): Promise<Provenance>
export function verifyArtifactProvenance(actual: unknown, expected: Provenance): void
