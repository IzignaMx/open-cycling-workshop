/** Source-owned host presentation, not a manifest, SDK or authorization interface. */
export interface OfficialModuleReference {
  readonly id: 'org.ocwp.module-information'
  readonly name: string
  readonly license: 'AGPL-3.0-only'
  readonly composition: 'explicit-build-import'
  readonly operationalMode: 'online-only'
  readonly permissions: readonly []
  readonly data: readonly []
  readonly secrets: readonly []
  readonly network: readonly []
}
const none = Object.freeze([]) as readonly []
export const officialModuleReference: OfficialModuleReference = Object.freeze({
  id: 'org.ocwp.module-information',
  name: 'Referencia de información del módulo integrado',
  license: 'AGPL-3.0-only',
  composition: 'explicit-build-import',
  operationalMode: 'online-only',
  permissions: none,
  data: none,
  secrets: none,
  network: none,
})
