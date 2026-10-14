import { THEMES, PALETTES, type ThemeId } from './catalog.js'
import { isSafeStoredLogo } from './logo.js'

export interface PresentationPreferences {
  schemaVersion: 1
  themeId: ThemeId
  paletteId: string
  scheme: 'theme' | 'light' | 'dark'
  density: 'comfortable' | 'workshop'
  logoDataUrl: string | null
}
export interface PreferenceScope {
  organizationId: string
  userId: string
  locationId: string | null
}
export const DEFAULT_PREFERENCES: Readonly<PresentationPreferences> = Object.freeze({
  schemaVersion: 1,
  themeId: 'banco',
  paletteId: 'bosque',
  scheme: 'theme',
  density: 'comfortable',
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
export function validatePreferences(value: unknown): {
  preferences: PresentationPreferences
  valid: boolean
} {
  const fallback = { preferences: { ...DEFAULT_PREFERENCES }, valid: false }
  if (typeof value !== 'object' || !value || Array.isArray(value)) return fallback
  const input = value as Record<string, unknown>
  const theme = THEMES.find((theme) => theme.id === input.themeId)
  if (
    input.schemaVersion !== 1 ||
    !theme ||
    !PALETTES.some((palette) => palette.id === input.paletteId) ||
    typeof input.scheme !== 'string' ||
    !['theme', 'light', 'dark'].includes(input.scheme) ||
    typeof input.density !== 'string' ||
    !['comfortable', 'workshop'].includes(input.density) ||
    (input.logoDataUrl !== null && !isSafeStoredLogo(input.logoDataUrl))
  )
    return fallback
  return {
    valid: true,
    preferences: {
      schemaVersion: 1,
      themeId: theme.id,
      paletteId: input.paletteId as string,
      scheme: input.scheme as PresentationPreferences['scheme'],
      density: input.density as PresentationPreferences['density'],
      logoDataUrl: input.logoDataUrl as string | null,
    },
  }
}
