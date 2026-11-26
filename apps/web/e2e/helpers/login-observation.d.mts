import type { Page } from '@playwright/test'

export function installLoginObserver(page: Page, origin: string): Promise<void>
export function observeLogin(
  page: Page,
  action: () => Promise<void>,
): Promise<{ bodyValidated: boolean; issuedMatchesStored: boolean }>
