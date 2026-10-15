import type { Page } from '@playwright/test'

export function isUnexpectedApiWrite(method: string, url: string): boolean
export function installInventoryContextObserver(page: Page): Promise<void>
export function observeInventoryContext(
  page: Page,
  locationId: string,
  action: () => Promise<void>,
): Promise<{ expiresAt: number; snapshotProtocol: null | 'baseline-v1' }>
