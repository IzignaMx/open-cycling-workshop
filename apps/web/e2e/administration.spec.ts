import AxeBuilder from '@axe-core/playwright'
import { expect, test, type APIRequestContext, type Page, type TestInfo } from '@playwright/test'
import type { UserResponse } from '@ocwp/api-client'
import { kernelSnapshot, PASSWORD, waitForReady } from './helpers/authenticated-workshop.js'

// Authentication and credential commands must not put even synthetic tokens or
// password request bodies in Playwright traces/video/failure screenshots.
// Explicit visual captures below occur only after credential controls are empty.
test.use({ trace: 'off', video: 'off', screenshot: 'off' })

// Keep order aligned with ADMINISTRATION_CASES in prepare_e2e_database.py.
const CASES = [
  'users',
  'scope',
  'zero',
  'no-sync',
  'empty',
  'logout',
  'password',
  'lost-response',
  'version',
  'owner',
  'themes',
  'selector-secret',
  'workshop-secret',
  'suspended-secret',
  'probe-secret',
  'visual-states',
] as const
type Case = (typeof CASES)[number]
const OWNER = 'e2e-administration-owner'
const HEADERS = { 'X-OCWP-Write-Protocol': '1' }

function fixture(name: Case, info: TestInfo) {
  // Never silently share a tenant on an unexpectedly expanded retry policy.
  expect(info.retry).toBeLessThan(2)
  const base = 10000 + info.retry * 1000 + CASES.indexOf(name) * 10
  const id = (entity: number) =>
    `00000000-0000-7000-8000-${String(base + entity).padStart(12, '0')}`
  return { organizationId: id(0), locationA: id(1), locationB: id(2), ownerId: id(3) }
}
type Fixture = ReturnType<typeof fixture>
async function token(
  request: APIRequestContext,
  f: Fixture,
  username = OWNER,
  password = PASSWORD,
) {
  const result = await request.post('/api/v1/auth/login', {
    data: { organization_id: f.organizationId, username, password },
  })
  expect(result.status()).toBe(200)
  return ((await result.json()) as { access_token: string }).access_token
}
function authorization(accessToken: string) {
  return { ...HEADERS, Authorization: `Bearer ${accessToken}` }
}
async function actor(
  request: APIRequestContext,
  f: Fixture,
  options: { role?: string; capabilities?: string[]; locationId?: string | null } = {},
) {
  const ownerToken = await token(request, f)
  const username = `e2e-case-${crypto.randomUUID()}`
  const result = await request.post('/api/v1/admin/users', {
    headers: authorization(ownerToken),
    data: {
      username,
      display_name: username,
      password: PASSWORD,
      location_id: options.locationId ?? null,
      ...(options.capabilities
        ? { capabilities: options.capabilities }
        : { role: options.role ?? 'Owner' }),
    },
  })
  expect(result.status()).toBe(201)
  return (await result.json()) as UserResponse
}
async function loginAccount(page: Page, f: Fixture, username = OWNER, password = PASSWORD) {
  await page.goto('/')
  await page.getByLabel('Organización', { exact: true }).fill(f.organizationId)
  await page.getByLabel('Usuario', { exact: true }).fill(username)
  await page.getByLabel('Contraseña', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(
    page.locator('[data-runtime-state="SELECTOR"], [data-runtime-state="READY"]'),
  ).toBeVisible({ timeout: 20_000 })
  await expect(
    page
      .getByRole('button', { name: 'Verificar acceso a administración', exact: true })
      .or(page.getByRole('heading', { name: 'Mi sesión', exact: true })),
  ).toBeVisible()
}
async function openAdministration(page: Page) {
  await expect(
    page.locator('[data-runtime-state="SELECTOR"], [data-runtime-state="READY"]'),
  ).toBeVisible({ timeout: 20_000 })
  const verify = page.getByRole('button', {
    name: 'Verificar acceso a administración',
    exact: true,
  })
  await expect(
    verify.or(page.getByRole('heading', { name: 'Mi sesión', exact: true })),
  ).toBeVisible()
  const sessionHeading = page.getByRole('heading', { name: 'Mi sesión', exact: true })
  await expect
    .poll(
      async () =>
        (await sessionHeading.isVisible()) ||
        ((await verify.isVisible()) && (await verify.isEnabled())),
    )
    .toBe(true)
  if (!(await sessionHeading.isVisible())) await verify.click()
  await expect(page.getByRole('heading', { name: 'Mi sesión', exact: true })).toBeVisible()
}
async function loadUsers(page: Page) {
  await page.getByRole('button', { name: 'Cargar usuarios', exact: true }).click()
}
async function expectSecretNotPersisted(page: Page, secret: string) {
  const found = await page.evaluate(async (value) => {
    if (JSON.stringify({ ...localStorage, ...sessionStorage }).includes(value)) return true
    for (const entry of await indexedDB.databases()) {
      if (!entry.name) continue
      const open = indexedDB.open(entry.name)
      open.onupgradeneeded = () => open.transaction!.abort()
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        open.onsuccess = () => resolve(open.result)
        open.onerror = () => reject(open.error)
      })
      try {
        for (const store of Array.from(db.objectStoreNames)) {
          const request = db.transaction(store, 'readonly').objectStore(store).getAll()
          const rows = await new Promise<unknown>((resolve, reject) => {
            request.onsuccess = () => resolve(request.result)
            request.onerror = () => reject(request.error)
          })
          if (JSON.stringify(rows).includes(value)) return true
        }
      } finally {
        db.close()
      }
    }
    return false
  }, secret)
  expect(found, 'credential material must not enter browser persistence').toBe(false)
}
async function users(request: APIRequestContext, accessToken: string) {
  const response = await request.get('/api/v1/admin/users?limit=200', {
    headers: authorization(accessToken),
  })
  expect(response.status()).toBe(200)
  return ((await response.json()) as { items: UserResponse[] }).items
}

// These are actual production UI -> FastAPI -> PostgreSQL journeys. No response
// is manufactured; only the explicitly identified lost-response case intercepts
// delivery after the real server has committed.
test('creates a user and replaces that individual permission snapshot without changing the actor', async ({
  page,
  request,
}, info) => {
  const f = fixture('users', info)
  await loginAccount(page, f)
  await openAdministration(page)
  await loadUsers(page)
  await page.getByRole('button', { name: 'Crear usuario', exact: true }).click()
  const form = page.getByRole('form', { name: 'Crear usuario', exact: true })
  const username = `e2e-created-${crypto.randomUUID()}`
  await form.getByLabel('Nombre de usuario', { exact: true }).fill(username)
  await form.getByLabel('Nombre visible', { exact: true }).fill('Cuenta sintética creada')
  await form.getByLabel('Contraseña inicial', { exact: true }).fill(PASSWORD)
  await form.getByRole('combobox', { name: 'Rol', exact: true }).selectOption('TechnicalAdmin')
  const created = page.waitForResponse(
    (r) => r.url().endsWith('/api/v1/admin/users') && r.request().method() === 'POST',
  )
  await form.getByRole('button', { name: 'Guardar usuario', exact: true }).click()
  expect((await created).status()).toBe(201)
  await expect(form.getByLabel('Contraseña inicial', { exact: true })).toHaveValue('')
  await expectSecretNotPersisted(page, PASSWORD)
  await form.getByRole('button', { name: 'Descartar cambios de usuario', exact: true }).click()
  const ownerToken = await token(request, f)
  let target = (await users(request, ownerToken)).find((u) => u.username === username)!
  expect(target.capabilities).toEqual([])
  expect(target.is_owner).toBe(false)
  await loadUsers(page)
  await page
    .getByRole('article', { name: `Usuario ${username}`, exact: true })
    .getByRole('button', { name: 'Editar usuario', exact: true })
    .click()
  const edit = page.getByRole('form', { name: `Editar usuario ${username}`, exact: true })
  await edit.getByLabel('Nombre visible', { exact: true }).fill('Nombre revisado')
  await edit.getByRole('combobox', { name: 'Rol', exact: true }).selectOption('Viewer')
  await edit.getByLabel('Confirmo el cambio de seguridad', { exact: true }).check()
  const patched = page.waitForResponse(
    (r) => r.url().endsWith(`/admin/users/${target.user_id}`) && r.request().method() === 'PATCH',
  )
  await edit.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  expect((await patched).status()).toBe(200)
  target = (await users(request, ownerToken)).find((u) => u.username === username)!
  expect(target.display_name).toBe('Nombre revisado')
  expect(target.capabilities).toContain('customers.read')
  expect(target.capabilities).not.toContain('users.write')
  const current = await request.get('/api/v1/auth/me', { headers: authorization(ownerToken) })
  expect(current.status()).toBe(200)
  expect(((await current.json()) as { user_id: string }).user_id).toBe(f.ownerId)
})

test('zero-location owner creates a location without selecting an operational workshop', async ({
  page,
  request,
}, info) => {
  const f = fixture('zero', info)
  await loginAccount(page, f)
  await openAdministration(page)
  const name = `Nuevo taller ${crypto.randomUUID()}`
  await page.getByLabel('Nombre de ubicación', { exact: true }).fill(name)
  const created = page.waitForResponse(
    (r) => r.url().endsWith('/api/v1/locations') && r.request().method() === 'POST',
  )
  await page
    .getByRole('form', { name: 'Crear ubicación', exact: true })
    .getByRole('button', { name: 'Crear ubicación', exact: true })
    .click()
  expect((await created).status()).toBe(201)
  await expect(page.locator('[data-runtime-state="READY"]')).toHaveCount(0)
  const response = await request.get('/api/v1/locations', {
    headers: authorization(await token(request, f)),
  })
  expect(response.status()).toBe(200)
  expect((await response.json()).items).toEqual([expect.objectContaining({ name })])
})

for (const name of ['no-sync', 'empty'] as const) {
  test(`${name}: connected account controls need neither operational admission nor directory grants`, async ({
    page,
    request,
  }, info) => {
    const f = fixture(name, info)
    const identity = await actor(request, f, {
      locationId: f.locationA,
      capabilities: name === 'empty' ? [] : ['users.read'],
    })
    let baselineRequests = 0
    page.on('request', (r) => {
      if (new URL(r.url()).pathname.includes('/sync/baselines/')) baselineRequests++
    })
    await loginAccount(page, f, identity.username)
    await openAdministration(page)
    await page
      .getByRole('form', { name: 'Cambiar contraseña', exact: true })
      .getByLabel('Confirmo el cambio de seguridad', { exact: true })
      .check()
    await expect(
      page.getByRole('button', { name: 'Cerrar todas mis sesiones', exact: true }),
    ).toBeEnabled()
    await expect(page.locator('[data-runtime-state="READY"]')).toHaveCount(0)
    expect(baselineRequests).toBe(0)
    await expect(page.getByRole('form', { name: 'Crear ubicación', exact: true })).toHaveCount(0)
    if (name === 'empty')
      await expect(page.getByRole('button', { name: 'Cargar usuarios', exact: true })).toHaveCount(
        0,
      )
    await page.context().setOffline(true)
    await expect(page.getByRole('heading', { name: 'Mi sesión', exact: true })).toHaveCount(0)
  })
}

test('server-scoped directory excludes another workshop while organization-wide account keeps its scope after selecting A', async ({
  page,
  request,
}, info) => {
  const f = fixture('scope', info)
  const inA = await actor(request, f, { role: 'TechnicalAdmin', locationId: f.locationA })
  const inB = await actor(request, f, { role: 'TechnicalAdmin', locationId: f.locationB })
  const bound = await actor(request, f, { role: 'Administrator', locationId: f.locationA })
  await loginAccount(page, f, bound.username)
  await openAdministration(page)
  await loadUsers(page)
  await expect(
    page.getByRole('article', { name: `Usuario ${inA.username}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('article', { name: `Usuario ${inB.username}`, exact: true }),
  ).toHaveCount(0)
  await expect(page.getByRole('article', { name: `Usuario ${OWNER}`, exact: true })).toHaveCount(0)
  const denied = await request.patch(`/api/v1/admin/users/${inB.user_id}`, {
    headers: authorization(await token(request, f, bound.username)),
    data: { expected_version: inB.version, display_name: 'Fuera de ámbito' },
  })
  expect(denied.status()).toBe(403)
  await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
  await loginAccount(page, f)
  await page.getByRole('button', { name: 'Taller administración A', exact: true }).click()
  await waitForReady(page)
  const before = await kernelSnapshot(page)
  await openAdministration(page)
  await loadUsers(page)
  await expect(
    page.getByRole('article', { name: `Usuario ${inB.username}`, exact: true }),
  ).toBeVisible()
  const after = await kernelSnapshot(page)
  expect(after.context.accountLocationId).toBeNull()
  expect(after.partition.partitionId).toBe(before.partition.partitionId)
  expect(after.journal).toEqual(before.journal)
})

for (const action of ['logout', 'password'] as const) {
  test(`${action}: self-security closes the session and fresh login is required`, async ({
    page,
    request,
  }, info) => {
    const f = fixture(action, info)
    const identity = await actor(request, f, { capabilities: [] })
    const oldToken = await token(request, f, identity.username)
    await loginAccount(page, f, identity.username)
    await openAdministration(page)
    const replacement = 'synthetic-replacement-password'
    if (action === 'password') {
      await page.getByLabel('Contraseña actual', { exact: true }).fill(PASSWORD)
      await page.getByLabel('Nueva contraseña', { exact: true }).fill(replacement)
    }
    await page
      .getByRole('form', { name: 'Cambiar contraseña', exact: true })
      .getByLabel('Confirmo el cambio de seguridad', { exact: true })
      .check()
    const response = page.waitForResponse((r) =>
      r.url().endsWith(action === 'password' ? '/auth/change-password' : '/auth/logout-all'),
    )
    page.once('dialog', (dialog) => void dialog.accept())
    await page
      .getByRole('button', {
        name: action === 'password' ? 'Cambiar contraseña' : 'Cerrar todas mis sesiones',
        exact: true,
      })
      .click()
    expect((await response).status()).toBe(204)
    await expectSecretNotPersisted(page, PASSWORD)
    await expectSecretNotPersisted(page, replacement)
    await expect(page.getByRole('button', { name: 'Iniciar sesión', exact: true })).toBeVisible()
    expect(
      (await request.get('/api/v1/auth/me', { headers: authorization(oldToken) })).status(),
    ).toBe(401)
    await loginAccount(page, f, identity.username, action === 'password' ? replacement : PASSWORD)
    await openAdministration(page)
  })
}

test('real committed location response lost in transit remains unconfirmed and is never automatically retried', async ({
  page,
  request,
}, info) => {
  const f = fixture('lost-response', info)
  await loginAccount(page, f)
  await openAdministration(page)
  let writes = 0
  let committed = false
  await page.route('**/api/v1/locations', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    writes++
    const response = await route.fetch()
    expect(response.status()).toBe(201)
    committed = true
    await route.abort('failed')
  })
  const name = `Respuesta perdida ${crypto.randomUUID()}`
  await page.getByLabel('Nombre de ubicación', { exact: true }).fill(name)
  await page
    .getByRole('form', { name: 'Crear ubicación', exact: true })
    .getByRole('button', { name: 'Crear ubicación', exact: true })
    .click()
  await expect.poll(() => committed).toBe(true)
  await expect(page.getByRole('alert')).toContainText(/confirm|inciert/i)
  // A read after the failed delivery establishes persisted outcome independently;
  // it does not claim the UI can identify which command created a matching name.
  const response = await request.get('/api/v1/locations', {
    headers: authorization(await token(request, f)),
  })
  expect(
    (await response.json()).items.filter((l: { name: string }) => l.name === name),
  ).toHaveLength(1)
  await page.context().setOffline(true)
  await page.context().setOffline(false)
  await page.reload()
  await openAdministration(page)
  expect(writes).toBe(1)
})

test('stale editor receives the real version conflict and never overwrites the intervening change', async ({
  page,
  request,
}, info) => {
  const f = fixture('version', info)
  const target = await actor(request, f, { capabilities: [] })
  await loginAccount(page, f)
  await openAdministration(page)
  await loadUsers(page)
  await page
    .getByRole('article', { name: `Usuario ${target.username}`, exact: true })
    .getByRole('button', { name: 'Editar usuario', exact: true })
    .click()
  const edit = page.getByRole('form', { name: `Editar usuario ${target.username}`, exact: true })
  await edit.getByLabel('Nombre visible', { exact: true }).fill('Borrador anterior')
  const ownerToken = await token(request, f)
  expect(
    (
      await request.patch(`/api/v1/admin/users/${target.user_id}`, {
        headers: authorization(ownerToken),
        data: { expected_version: target.version, display_name: 'Cambio concurrente' },
      })
    ).status(),
  ).toBe(200)
  const conflict = page.waitForResponse(
    (r) => r.url().endsWith(`/admin/users/${target.user_id}`) && r.request().method() === 'PATCH',
  )
  await edit.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  expect((await conflict).status()).toBe(409)
  await expect(page.getByRole('alert')).toBeVisible()
  expect(
    (await users(request, ownerToken)).find((u) => u.user_id === target.user_id)?.display_name,
  ).toBe('Cambio concurrente')
})

test('grant bundle alone never permits protected owner administration', async ({
  page,
  request,
}, info) => {
  const f = fixture('owner', info)
  const nonOwner = await actor(request, f)
  await loginAccount(page, f, nonOwner.username)
  await openAdministration(page)
  await loadUsers(page)
  const row = page.getByRole('article', { name: `Usuario ${OWNER}`, exact: true })
  await expect(row).toBeVisible()
  await expect(row.getByRole('button', { name: 'Editar usuario', exact: true })).toBeDisabled()
  const response = await request.patch(`/api/v1/admin/users/${f.ownerId}`, {
    headers: authorization(await token(request, f, nonOwner.username)),
    data: { expected_version: 1, display_name: 'No autorizado' },
  })
  expect(response.status()).toBe(403)
})

const THEMES = ['Banco de trabajo', 'Plano técnico', 'Ritmo modular', 'Turno nocturno']
async function prepareFullPageCapture(page: Page) {
  // A translated fixed skip link can appear above a scrolled viewport in a
  // stitched full-page image. Capture from the document origin without blurring.
  await page.evaluate(() => window.scrollTo(0, 0))
  const skip = page.getByRole('link', { name: 'Saltar al contenido', exact: true })
  await expect(skip).not.toBeFocused()
  expect(
    await skip.evaluate((element) => element.getBoundingClientRect().bottom),
  ).toBeLessThanOrEqual(0)
}
async function expectReadableWorkshopSummary(page: Page) {
  const layout = await page.evaluate(() => {
    const zoom = Number(getComputedStyle(document.documentElement).zoom)
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')!
    const labels = Array.from(
      document.querySelectorAll<HTMLElement>(
        '.workshop-metrics dt, .workshop-identity strong, .settings-trigger, .workshop-links a',
      ),
    ).map((element) => {
      const style = getComputedStyle(element)
      context.font = style.font
      const text = element.textContent?.trim() ?? ''
      const longestWordWidth = Math.max(
        ...text.split(/\s+/).map((word) => context.measureText(word).width),
      )
      const availableWidth =
        element.getBoundingClientRect().width / zoom -
        parseFloat(style.paddingLeft) -
        parseFloat(style.paddingRight) -
        parseFloat(style.borderLeftWidth) -
        parseFloat(style.borderRightWidth)
      return { text, availableWidth, longestWordWidth }
    })
    const identity = document.querySelector('.workshop-identity strong')!
    const range = document.createRange()
    range.selectNodeContents(identity)
    return { labels, identityLines: range.getClientRects().length }
  })
  expect(layout.labels).toHaveLength(11) // four metrics, identity, settings, five links
  for (const label of layout.labels) {
    expect(
      label.availableWidth + 1,
      `readable complete words: ${label.text}`,
    ).toBeGreaterThanOrEqual(label.longestWordWidth)
  }
  expect(layout.identityLines, 'OCWP identity must remain on one readable line').toBe(1)
}
test('administration preserves mounted drafts across all themes with narrow reflow and accessible controls', async ({
  page,
}, info) => {
  test.setTimeout(120_000)
  const f = fixture('themes', info)
  await loginAccount(page, f)
  await page.getByRole('button', { name: 'Taller administración A', exact: true }).click()
  await waitForReady(page)
  await openAdministration(page)
  const input = page.getByLabel('Nombre de ubicación', { exact: true })
  await input.fill('Borrador de ubicación con texto ampliado')
  const handle = await input.elementHandle()
  await input.evaluate((e) => (e as HTMLInputElement).setSelectionRange(2, 7))
  for (const [index, theme] of THEMES.entries()) {
    await page.getByRole('button', { name: 'Personalización', exact: true }).click()
    await page.getByRole('radio', { name: new RegExp(theme) }).check()
    await page.getByRole('button', { name: 'Cerrar personalización', exact: true }).click()
    expect(await handle!.evaluate((e) => e.isConnected)).toBe(true)
    await expect(input).toHaveValue('Borrador de ubicación con texto ampliado')
    expect(await input.evaluate((e) => (e as HTMLInputElement).selectionStart)).toBe(2)
    for (const width of [1440, 834, 320]) {
      await page.setViewportSize({ width, height: 1000 })
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true)
      if (width === 320) await expectReadableWorkshopSummary(page)
      const accessibility = await new AxeBuilder({ page }).analyze()
      expect(
        accessibility.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? '')),
      ).toEqual([])
      const path = info.outputPath(`administration-theme-${index}-${width}.png`)
      await prepareFullPageCapture(page)
      await page.screenshot({ path, fullPage: true })
      await info.attach(`administration-theme-${index}-${width}`, {
        path,
        contentType: 'image/png',
      })
    }
    // CSS enlargement changes available layout width without changing viewport media queries.
    await page.setViewportSize({ width: 640, height: 1000 })
    await page.evaluate(() => {
      document.documentElement.style.zoom = '2'
    })
    expect(
      await page.evaluate(() => ({
        innerWidth: window.innerWidth,
        effectiveCssWidth:
          window.innerWidth / Number(getComputedStyle(document.documentElement).zoom),
        noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth,
      })),
    ).toEqual({ innerWidth: 640, effectiveCssWidth: 320, noHorizontalOverflow: true })
    await expectReadableWorkshopSummary(page)
    expect(await handle!.evaluate((element) => element.isConnected)).toBe(true)
    await expect(input).toHaveValue('Borrador de ubicación con texto ampliado')
    const zoomThemePath = info.outputPath(`administration-theme-${index}-200-percent.png`)
    await prepareFullPageCapture(page)
    await page.screenshot({ path: zoomThemePath, fullPage: true })
    await info.attach(`administration-theme-${index}-200-percent`, {
      path: zoomThemePath,
      contentType: 'image/png',
    })
    await page.evaluate(() => {
      document.documentElement.style.zoom = '1'
    })
    await page.setViewportSize({ width: 320, height: 1000 })
  }
  await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' })
  await input.focus()
  await page.keyboard.press('Tab')
  const create = page
    .getByRole('form', { name: 'Crear ubicación', exact: true })
    .getByRole('button', { name: 'Crear ubicación', exact: true })
  await expect(create).toBeFocused()
  const box = await create.boundingBox()
  expect(box!.width).toBeGreaterThanOrEqual(44)
  expect(box!.height).toBeGreaterThanOrEqual(44)
  // Separate the already-asserted true 320px unzoomed viewport from CSS
  // enlargement: 640px / 200% = 320 effective CSS pixels. This does not
  // claim support at 160 CSS pixels or physical browser/device zoom.
  await page.setViewportSize({ width: 640, height: 1000 })
  await page.evaluate(() => {
    document.documentElement.style.zoom = '2'
  })
  const zoomGeometry = await page.evaluate(() => {
    const zoom = Number(getComputedStyle(document.documentElement).zoom)
    return {
      innerWidth: window.innerWidth,
      zoom,
      effectiveCssWidth: window.innerWidth / zoom,
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth,
    }
  })
  expect(zoomGeometry).toEqual({
    innerWidth: 640,
    zoom: 2,
    effectiveCssWidth: 320,
    noHorizontalOverflow: true,
  })
  await expect(create).toBeFocused()
  await expectReadableWorkshopSummary(page)
  const zoomPath = info.outputPath('administration-forced-colors-200-percent.png')
  await prepareFullPageCapture(page)
  await expect(create).toBeFocused()
  await page.screenshot({ path: zoomPath, fullPage: true })
  await info.attach('administration-forced-colors-200-percent', {
    path: zoomPath,
    contentType: 'image/png',
  })
  await page.evaluate(() => {
    document.documentElement.style.zoom = '1'
  })
  await page.setViewportSize({ width: 320, height: 1000 })
  expect(
    await page.evaluate(() => ({
      innerWidth: window.innerWidth,
      zoom: Number(getComputedStyle(document.documentElement).zoom),
    })),
  ).toEqual({ innerWidth: 320, zoom: 1 })
  await page.evaluate(() => {
    // Synthetic label expansion is layout evidence, not a translation claim.
    for (const element of document.querySelectorAll(
      '.administration-panel h1, .administration-panel h2, .administration-panel button, .administration-panel label',
    )) {
      for (const child of Array.from(element.childNodes)) {
        if (child.nodeType === Node.TEXT_NODE && child.textContent?.trim()) {
          const text = child.textContent
          child.textContent = text + ' ampliación'.repeat(Math.ceil((text.length * 0.35) / 11))
        }
      }
    }
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  const expandedPath = info.outputPath('administration-expanded-labels-320.png')
  await prepareFullPageCapture(page)
  await expect(create).toBeFocused()
  await page.screenshot({ path: expandedPath, fullPage: true })
  await info.attach('administration-expanded-labels-320', {
    path: expandedPath,
    contentType: 'image/png',
  })
})

// The following finite intercepted journeys qualify UI lifecycle behavior only.
// They do not substitute for real server authorization/concurrency proofs above.
test('UI lifecycle: selector offline event and account replacement synchronously clear mounted secrets', async ({
  page,
  request,
}, info) => {
  const f = fixture('selector-secret', info)
  const first = await actor(request, f, { capabilities: [] })
  const second = await actor(request, f, { capabilities: [] })
  await loginAccount(page, f, first.username)
  await openAdministration(page)
  const secret = 'synthetic-selector-secret'
  const input = page.getByLabel('Nueva contraseña', { exact: true })
  await input.fill(secret)
  const handle = await input.elementHandle()
  // Read the same node in the same event turn, before React's next render.
  expect(
    await input.evaluate((element) => {
      window.dispatchEvent(new Event('offline'))
      return (element as HTMLInputElement).value
    }),
  ).toBe('')
  await expect(page.getByRole('heading', { name: 'Mi sesión', exact: true })).toHaveCount(0)
  expect(await handle!.evaluate((element) => (element as HTMLInputElement).value)).toBe('')
  await expectSecretNotPersisted(page, secret)
  await openAdministration(page)
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(secret)
  const replacementHandle = await page
    .getByLabel('Nueva contraseña', { exact: true })
    .elementHandle()
  page.once('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: 'Cerrar sesión en este dispositivo', exact: true }).click()
  expect(await replacementHandle!.evaluate((element) => (element as HTMLInputElement).value)).toBe(
    '',
  )
  await loginAccount(page, f, second.username)
  await openAdministration(page)
  await expect(page.getByLabel('Nueva contraseña', { exact: true })).toHaveValue('')
  await expectSecretNotPersisted(page, secret)
})

test('UI lifecycle: administration navigation preserves operational nodes; workshop switch clears secret controls', async ({
  page,
}, info) => {
  const f = fixture('workshop-secret', info)
  await loginAccount(page, f)
  await page.getByRole('button', { name: 'Taller administración A', exact: true }).click()
  await waitForReady(page)
  const before = await kernelSnapshot(page)
  const operational = page.getByLabel('Nombre', { exact: true })
  await operational.fill('Borrador operativo conservado')
  const node = await operational.elementHandle()
  await operational.evaluate((element) => (element as HTMLInputElement).setSelectionRange(2, 6))
  await page.getByRole('link', { name: 'Administración', exact: true }).click()
  await openAdministration(page)
  await page.getByRole('link', { name: 'Resumen', exact: true }).click()
  expect(await node!.evaluate((element) => element.isConnected)).toBe(true)
  expect(await node!.evaluate((element) => (element as HTMLInputElement).selectionStart)).toBe(2)
  await expect(operational).toHaveValue('Borrador operativo conservado')
  expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
  const secret = 'synthetic-workshop-secret'
  const password = page.getByLabel('Nueva contraseña', { exact: true })
  await password.fill(secret)
  const passwordNode = await password.elementHandle()
  page.once('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: 'Cambiar taller', exact: true }).click()
  expect(await passwordNode!.evaluate((element) => (element as HTMLInputElement).value)).toBe('')
  await page.getByRole('button', { name: 'Taller administración B', exact: true }).click()
  await waitForReady(page)
  await openAdministration(page)
  await expect(page.getByLabel('Nueva contraseña', { exact: true })).toHaveValue('')
  expect((await kernelSnapshot(page, before.partition.partitionId)).journal).toEqual(before.journal)
  await expectSecretNotPersisted(page, secret)
})

test('UI lifecycle: self-command suspends before dispatch and uncertain delivery never restores old admission', async ({
  page,
}, info) => {
  const f = fixture('suspended-secret', info)
  await loginAccount(page, f)
  await page.getByRole('button', { name: 'Taller administración A', exact: true }).click()
  await waitForReady(page)
  await openAdministration(page)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let dispatched = false
  await page.route('**/api/v1/auth/change-password', async (route) => {
    dispatched = true
    await gate
    // No server mutation is sent in this UI-only uncertainty test.
    await route.abort('failed')
  })
  const secret = 'synthetic-suspended-secret'
  await page.getByLabel('Contraseña actual', { exact: true }).fill(PASSWORD)
  const next = page.getByLabel('Nueva contraseña', { exact: true })
  await next.fill(secret)
  const handle = await next.elementHandle()
  await page
    .getByRole('form', { name: 'Cambiar contraseña', exact: true })
    .getByLabel('Confirmo el cambio de seguridad', { exact: true })
    .check()
  page.once('dialog', (dialog) => void dialog.accept())
  try {
    await page.getByRole('button', { name: 'Cambiar contraseña', exact: true }).click()
    await expect.poll(() => dispatched).toBe(true)
    await expect(page.locator('[data-runtime-state="READY"]')).toHaveCount(0)
    expect(await handle!.evaluate((element) => (element as HTMLInputElement).value)).toBe('')
    await expectSecretNotPersisted(page, secret)
    release()
    await expect(page.getByRole('button', { name: 'Iniciar sesión', exact: true })).toBeVisible()
    await expect(page.locator('[data-runtime-state="READY"]')).toHaveCount(0)
  } finally {
    release()
    await page.unrouteAll({ behavior: 'wait' })
  }
})

test('UI lifecycle: automatic probe revalidation clears a newly entered administration secret', async ({
  page,
}, info) => {
  const f = fixture('probe-secret', info)
  await loginAccount(page, f)
  await page.getByRole('button', { name: 'Taller administración A', exact: true }).click()
  await waitForReady(page)
  await page.clock.install()
  await page.clock.pauseAt(new Date())
  // A synthetic offline event leaves LAN requests reachable, modeling the
  // runtime's existing navigator-offline-but-server-reachable probe seam.
  await page.evaluate(() => window.dispatchEvent(new Event('offline')))
  await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
  await openAdministration(page)
  const secret = 'synthetic-probe-secret'
  const input = page.getByLabel('Nueva contraseña', { exact: true })
  await input.fill(secret)
  const handle = await input.elementHandle()
  const contextRequest = page.waitForRequest('**/api/v1/auth/context*')
  await page.clock.runFor(2100)
  await contextRequest
  await expect
    .poll(() => handle!.evaluate((element) => (element as HTMLInputElement).value))
    .toBe('')
  await expect(page.getByRole('heading', { name: 'Mi sesión', exact: true })).toHaveCount(0)
  await expectSecretNotPersisted(page, secret)
  await page.clock.resume()
})

async function captureAdministration(page: Page, info: TestInfo, name: string) {
  // Never attach a screenshot with a mounted nonempty credential input.
  expect(
    await page
      .locator('input[type="password"]')
      .evaluateAll((inputs) => inputs.every((input) => (input as HTMLInputElement).value === '')),
  ).toBe(true)
  const path = info.outputPath(`${name}.png`)
  await page.locator('.administration-panel').screenshot({ path })
  await info.attach(name, { path, contentType: 'image/png' })
}

test('UI visual states: each theme captures directory, editor, security review, error and uncertain result', async ({
  page,
  request,
}, info) => {
  test.setTimeout(120_000)
  const f = fixture('visual-states', info)
  const target = await actor(request, f, { capabilities: [] })
  await loginAccount(page, f)
  await page.getByRole('button', { name: 'Taller administración A', exact: true }).click()
  await waitForReady(page)
  await openAdministration(page)
  await loadUsers(page)
  await page.route(`**/api/v1/admin/users/${target.user_id}`, (route) =>
    route.fulfill({
      status: 409,
      headers: { 'Cache-Control': 'no-store' },
      json: { error: { code: 'stale_user_version' } },
    }),
  )
  await page.route('**/api/v1/locations', (route) =>
    route.request().method() === 'POST' ? route.abort('failed') : route.continue(),
  )
  for (const [index, theme] of THEMES.entries()) {
    await page.getByRole('button', { name: 'Personalización', exact: true }).click()
    const choice = page.getByRole('radio', { name: new RegExp(theme) })
    await choice.focus()
    await choice.press('Space')
    await expect(choice).toBeFocused()
    await choice.press('Escape')
    await expect(page.getByRole('button', { name: 'Personalización', exact: true })).toBeFocused()
    await captureAdministration(page, info, `admin-${index}-directory`)
    await page
      .getByRole('article', { name: `Usuario ${target.username}`, exact: true })
      .getByRole('button', { name: 'Editar usuario', exact: true })
      .click()
    const form = page.getByRole('form', { name: `Editar usuario ${target.username}`, exact: true })
    await form.getByLabel('Nombre visible', { exact: true }).fill('Borrador visual')
    await captureAdministration(page, info, `admin-${index}-editor`)
    await form.getByRole('combobox', { name: 'Rol', exact: true }).selectOption('Viewer')
    await form.getByLabel('Confirmo el cambio de seguridad', { exact: true }).check()
    await captureAdministration(page, info, `admin-${index}-security-review`)
    await form.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('La cuenta cambió')
    await captureAdministration(page, info, `admin-${index}-version-error`)
    await form.getByRole('button', { name: 'Descartar cambios de usuario', exact: true }).click()
    await page.getByLabel('Nombre de ubicación', { exact: true }).fill('Resultado visual incierto')
    await page
      .getByRole('form', { name: 'Crear ubicación', exact: true })
      .getByRole('button', { name: 'Crear ubicación', exact: true })
      .click()
    await expect(page.getByRole('alert')).toContainText('Resultado sin confirmar')
    await captureAdministration(page, info, `admin-${index}-unknown-result`)
  }
})
