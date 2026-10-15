import { THEMES, PALETTES, type ThemeId } from './catalog.js'
import { isSafeStoredLogo } from './logo.js'

export interface PresentationPreferences {
  schemaVersion: 2
  themeId: ThemeId
  paletteId: string
  paletteSource: 'personal' | 'workshop'
  scheme: 'theme' | 'light' | 'dark'
  density: 'comfortable' | 'workshop'
  logoMode: 'local' | 'none' | 'workshop'
  logoDataUrl: string | null
}
export interface PreferenceScope {
  organizationId: string
  userId: string
  locationId: string | null
}
export const DEFAULT_PREFERENCES: Readonly<PresentationPreferences> = Object.freeze({
  schemaVersion: 2,
  themeId: 'banco',
  paletteId: 'bosque',
  paletteSource: 'workshop',
  scheme: 'theme',
  density: 'comfortable',
  logoMode: 'workshop',
  logoDataUrl: null,
})
export function preferenceScopeKey(
  scope: PreferenceScope,
  kind: 'appearance' | 'logo' = 'appearance',
): string {
  return JSON.stringify(
    kind === 'appearance'
      ? [kind, scope.organizationId, scope.userId]
      : [kind, scope.organizationId, scope.userId, scope.locationId],
  )
}
function exactKeys(input: Record<string, unknown>, fields: readonly string[]): boolean {
  return (
    Object.keys(input).length === fields.length &&
    fields.every((field) => Object.hasOwn(input, field))
  )
}
export interface LogoPreference {
  schemaVersion: 2
  logoMode: PresentationPreferences['logoMode']
  logoDataUrl: string | null
}
/** Absence is handled by the repository: a stored null records an explicit removal. */
export function validateLogoPreference(value: unknown): LogoPreference | null {
  if (value === null || isSafeStoredLogo(value))
    return { schemaVersion: 2, logoMode: value === null ? 'none' : 'local', logoDataUrl: value }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const input = value as Record<string, unknown>
  if (
    !exactKeys(input, ['schemaVersion', 'logoMode', 'logoDataUrl']) ||
    input.schemaVersion !== 2 ||
    !['local', 'none', 'workshop'].some((mode) => mode === input.logoMode) ||
    (input.logoMode === 'local' ? !isSafeStoredLogo(input.logoDataUrl) : input.logoDataUrl !== null)
  )
    return null
  return {
    schemaVersion: 2,
    logoMode: input.logoMode as LogoPreference['logoMode'],
    logoDataUrl: input.logoDataUrl as string | null,
  }
}
export function validatePreferences(value: unknown): {
  preferences: PresentationPreferences
  valid: boolean
} {
  const fallback = { preferences: { ...DEFAULT_PREFERENCES }, valid: false }
  if (typeof value !== 'object' || !value || Array.isArray(value)) return fallback
  const input = value as Record<string, unknown>
  const fields = ['schemaVersion', 'themeId', 'paletteId', 'scheme', 'density', 'logoDataUrl']
  if (input.schemaVersion === 2) fields.push('paletteSource', 'logoMode')
  const theme = THEMES.find((theme) => theme.id === input.themeId)
  if (
    !exactKeys(input, fields) ||
    (input.schemaVersion !== 1 && input.schemaVersion !== 2) ||
    !theme ||
    !PALETTES.some((palette) => palette.id === input.paletteId) ||
    !['theme', 'light', 'dark'].some((scheme) => scheme === input.scheme) ||
    !['comfortable', 'workshop'].some((density) => density === input.density) ||
    (input.schemaVersion === 2 &&
      input.paletteSource !== 'personal' &&
      input.paletteSource !== 'workshop')
  )
    return fallback
  const logo = validateLogoPreference(
    input.schemaVersion === 1
      ? input.logoDataUrl
      : {
          schemaVersion: 2,
          logoMode: input.logoMode,
          logoDataUrl: input.logoDataUrl,
        },
  )
  if (!logo) return fallback
  return {
    valid: true,
    preferences: {
      schemaVersion: 2,
      themeId: theme.id,
      paletteId: input.paletteId as string,
      // A persisted v1 default palette is still an explicit historical choice.
      paletteSource:
        input.schemaVersion === 1
          ? 'personal'
          : (input.paletteSource as PresentationPreferences['paletteSource']),
      scheme: input.scheme as PresentationPreferences['scheme'],
      density: input.density as PresentationPreferences['density'],
      logoMode: logo.logoMode,
      logoDataUrl: logo.logoDataUrl,
    },
  }
}
