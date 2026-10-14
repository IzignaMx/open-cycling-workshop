import { createKernelDatabase } from '../../src/access-kernel/database.js'
import { seedLegacyFixture } from './legacy-fixture.js'
import { OcwpDatabase } from '../../src/local/db.js'
import { AccessKernel } from '../../src/access-kernel/kernel.js'

import { completedMetadata } from './qualified-fixture.js'
import { openBaselineQualification } from './baseline-qualification.js'

// This entrypoint is built only by the separate browser-test config, never the PWA.
const harness = {
  createKernelDatabase,
  AccessKernel,
  OcwpDatabase,
  seedLegacyFixture,
  completedMetadata,
  openBaselineQualification,
}
declare global {
  interface Window {
    kernelHarness: typeof harness
  }
}
window.kernelHarness = harness
