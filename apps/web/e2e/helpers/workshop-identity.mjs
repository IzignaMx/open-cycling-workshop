import { expect } from '@playwright/test'

/** @param {import('@playwright/test').Page} page @param {string} expectedIdentity */
export async function expectWorkshopIdentity(page, expectedIdentity) {
  // READY covers operational admission, not asynchronous shared presentation.
  // allTextContents samples immediately: absence cannot add a locator wait.
  // Array equality also rejects duplicate identity nodes. Inherit the suite's
  // assertion timeout; do not introduce a second budget or a fixed sleep.
  await expect
    .poll(() => page.locator('.workshop-identity strong').allTextContents())
    .toEqual([expectedIdentity])
}
