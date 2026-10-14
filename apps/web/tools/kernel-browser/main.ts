import { BrandingSnapshotRepository } from '../../src/branding/cache.js'
import { PreferenceRepository } from '../../src/personalization/repository.js'
import {
  copyOwnedLegacyPreferences,
  inspectLegacyWork,
} from '../../src/runtime/legacy-preservation.js'
import { createKernelDatabase } from '../../src/access-kernel/database.js'
import { seedLegacyFixture } from './legacy-fixture.js'
import { OcwpDatabase } from '../../src/local/db.js'
import { AccessKernel } from '../../src/access-kernel/kernel.js'

import { completedMetadata } from './qualified-fixture.js'
import { openBaselineQualification } from './baseline-qualification.js'
import { openSupportedBaselineQualification } from './supported-baseline-qualification.js'

// This entrypoint is built only by the separate browser-test config, never the PWA.
const harness = {
  BrandingSnapshotRepository,
  PreferenceRepository,
  copyOwnedLegacyPreferences,
  inspectLegacyWork,
  createKernelDatabase,
  AccessKernel,
  OcwpDatabase,
  seedLegacyFixture,
  completedMetadata,
  openBaselineQualification,
  openSupportedBaselineQualification,
}
declare global {
  interface Window {
    kernelHarness: typeof harness
  }
}
window.kernelHarness = harness
