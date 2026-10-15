import type { BrandingProfile } from '../features/branding/contracts.js'
import { DEFAULT_PREFERENCES, type PresentationPreferences } from './preferences.js'

/** Render-only composition of already admitted branding. Never persist this result. */
export function resolvePresentation(
  preferences: PresentationPreferences,
  shared: BrandingProfile | null,
  fallbackName: string,
): { preferences: PresentationPreferences; displayName: string; shared: boolean } {
  const logo =
    preferences.logoMode === 'local'
      ? preferences.logoDataUrl
      : preferences.logoMode === 'workshop' &&
          shared?.logo_state === 'available' &&
          shared.logo?.png_base64
        ? `data:image/png;base64,${shared.logo.png_base64}`
        : null
  return {
    preferences: {
      ...preferences,
      paletteId:
        preferences.paletteSource === 'personal'
          ? preferences.paletteId
          : (shared?.palette_id ?? DEFAULT_PREFERENCES.paletteId),
      logoDataUrl: logo,
    },
    displayName: shared?.display_name ?? (fallbackName.trim() || 'OCWP'),
    shared: shared !== null && shared.version > 0,
  }
}
