import type { Page } from '@playwright/test'

export function expectWorkshopIdentity(page: Page, expectedIdentity: string): Promise<void>
