import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const width of [1440, 320]) {
  test(`public presentation: ${width}px subpath, keyboard, assets and accessibility`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    const unexpected: string[] = []
    const failed: string[] = []
    page.on('request', (request) => {
      if (!request.url().startsWith('http://127.0.0.1:5181/open-cycling-workshop/')) {
        unexpected.push(request.url())
      }
    })
    page.on('response', (response) => {
      if (response.status() >= 400) failed.push(response.url())
    })
    page.on('requestfailed', (request) => failed.push(request.url()))
    await page.goto('./')
    await expect(page.getByRole('heading', { level: 1 })).toContainText('El trabajo avanza')
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Saltar al contenido' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('main')).toBeFocused()
    const architectureLink = page.locator('#arquitectura .light-link')
    for (let index = 0; index < 80; index += 1) {
      if (await architectureLink.evaluate((element) => element === document.activeElement)) break
      await page.keyboard.press('Tab')
    }
    await expect(architectureLink).toBeFocused()
    const focus = await architectureLink.evaluate((element) => {
      const style = getComputedStyle(element)
      return { color: style.outlineColor, width: style.outlineWidth, style: style.outlineStyle }
    })
    expect(focus).toEqual({ color: 'rgb(225, 243, 195)', width: '3px', style: 'solid' })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    expect(
      await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior),
    ).toBe('auto')
    for (const image of await page.locator('img').all()) {
      await image.scrollIntoViewIfNeeded()
      await expect(image).toHaveJSProperty('complete', true)
      expect(
        await image.evaluate((element: HTMLImageElement) => element.naturalWidth),
      ).toBeGreaterThan(0)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const scan = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze()
    expect(scan.violations).toEqual([])
    await page.evaluate(() => scrollTo(0, 0))
    const screenshot = info.outputPath(`public-site-${width}.png`)
    await page.screenshot({ path: screenshot, fullPage: true })
    await info.attach(`public-site-${width}`, { path: screenshot, contentType: 'image/png' })
    expect(unexpected).toEqual([])
    expect(failed).toEqual([])
  })
}
