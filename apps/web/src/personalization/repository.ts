import {
  DEFAULT_PREFERENCES,
  preferenceScopeKey,
  validatePreferences,
  validateLogoPreference,
  type PreferenceScope,
  type PresentationPreferences,
} from './preferences.js'
import { isSafeStoredLogo } from './logo.js'

export interface PreferenceRecord {
  key: string
  organizationId: string
  userId: string
  locationId: string | null
  kind: 'appearance' | 'logo'
  value: unknown
}
interface PreferenceTable {
  get(key: string): Promise<unknown>
  put(record: PreferenceRecord): Promise<unknown>
}
// Shared across repository/component mounts for this table instance. Identity changes
// cannot let an older deferred write overtake a newer mount's preference.
const pendingWrites = new WeakMap<PreferenceTable, Map<string, Promise<void>>>()
function writesFor(table: PreferenceTable): Map<string, Promise<void>> {
  let writes = pendingWrites.get(table)
  if (!writes) {
    writes = new Map()
    pendingWrites.set(table, writes)
  }
  return writes
}

function scopedRecord(
  record: unknown,
  scope: PreferenceScope,
  kind: 'appearance' | 'logo',
): record is PreferenceRecord {
  if (!record || typeof record !== 'object') return false
  const row = record as Record<string, unknown>
  return (
    row.key === preferenceScopeKey(scope, kind) &&
    row.kind === kind &&
    row.organizationId === scope.organizationId &&
    row.userId === scope.userId &&
    row.locationId === (kind === 'logo' ? scope.locationId : null)
  )
}
/** Personal appearance follows the user within the organization; local logos also belong to a location. */
export class PreferenceRepository {
  constructor(private readonly table: PreferenceTable) {}
  private write(scope: PreferenceScope, record: PreferenceRecord): Promise<void> {
    const writes = writesFor(this.table)
    const key = preferenceScopeKey(scope)
    const previous = writes.get(key) ?? Promise.resolve()
    const pending = previous
      .catch(() => undefined)
      .then(async () => {
        await this.table.put(record)
      })
    writes.set(key, pending)
    void pending
      .finally(() => {
        if (writes.get(key) === pending) writes.delete(key)
      })
      .catch(() => undefined)
    return pending
  }
  async load(scope: PreferenceScope) {
    await writesFor(this.table)
      .get(preferenceScopeKey(scope))
      ?.catch(() => undefined)
    const [appearance, logo] = await Promise.all([
      this.table.get(preferenceScopeKey(scope)),
      this.table.get(preferenceScopeKey(scope, 'logo')),
    ])
    if (appearance !== undefined && !scopedRecord(appearance, scope, 'appearance'))
      return validatePreferences(null)
    if (logo !== undefined && !scopedRecord(logo, scope, 'logo')) return validatePreferences(null)
    const value =
      appearance === undefined ? DEFAULT_PREFERENCES : (appearance as PreferenceRecord).value
    const checked = validatePreferences(value)
    if (!checked.valid) return checked
    const checkedLogo =
      logo === undefined
        ? { logoMode: 'workshop' as const, logoDataUrl: null }
        : validateLogoPreference((logo as PreferenceRecord).value)
    if (!checkedLogo) return validatePreferences(null)
    return {
      valid: true,
      preferences: {
        ...checked.preferences,
        logoMode: checkedLogo.logoMode,
        logoDataUrl: checkedLogo.logoDataUrl,
      },
    }
  }
  async saveAppearance(
    scope: PreferenceScope,
    preferences: PresentationPreferences,
  ): Promise<void> {
    const checked = validatePreferences({ ...preferences, logoMode: 'workshop', logoDataUrl: null })
    if (!checked.valid) throw new Error('La preferencia visual es inválida.')
    await this.write(scope, {
      organizationId: scope.organizationId,
      userId: scope.userId,
      locationId: null,
      kind: 'appearance',
      key: preferenceScopeKey(scope),
      value: checked.preferences,
    })
  }
  async saveLogo(scope: PreferenceScope, logoDataUrl: string | null): Promise<void> {
    if (logoDataUrl !== null && !isSafeStoredLogo(logoDataUrl))
      throw new Error('La imagen local es inválida.')
    await this.write(scope, {
      ...scope,
      kind: 'logo',
      key: preferenceScopeKey(scope, 'logo'),
      value: { schemaVersion: 2, logoMode: logoDataUrl === null ? 'none' : 'local', logoDataUrl },
    })
  }
  async saveLogoMode(scope: PreferenceScope, mode: 'workshop' | 'none'): Promise<void> {
    if (mode !== 'workshop' && mode !== 'none') throw new Error('El modo de logo es inválido.')
    await this.write(scope, {
      ...scope,
      kind: 'logo',
      key: preferenceScopeKey(scope, 'logo'),
      value: { schemaVersion: 2, logoMode: mode, logoDataUrl: null },
    })
  }
}
