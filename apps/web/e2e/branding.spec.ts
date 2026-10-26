import AxeBuilder from '@axe-core/playwright'
import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
  type TestInfo,
} from '@playwright/test'
import type { BrandingProfile, BrandingPutRequest } from '../src/features/branding/contracts.js'
import type { BrandingSnapshot } from '../src/branding/cache.js'
import { PALETTES } from '../src/personalization/catalog.js'
import {
  DATABASE,
  PASSWORD,
  createCustomer,
  kernelSnapshot,
  waitForReady,
} from './helpers/authenticated-workshop.js'

// Only explicitly labelled, credential-empty screenshots are attached. Automatic
// login traces/video/screenshots could disclose even these synthetic credentials.
test.use({ trace: 'off', video: 'off', screenshot: 'off' })

// Exact order is checked against scripts/e2e/branding_fixtures.py. Every test and
// configured retry owns an independent disposable tenant, including legacy grants.
const CASES = [
  'convergence',
  'offline',
  'grants-none',
  'grants-legacy',
  'grants-read',
  'grants-write',
  'grants-legacy-read',
  'grants-legacy-write',
  'grants-both',
  'grants-concrete-old',
  'grants-technical',
  'conflict',
  'unconfirmed',
  'scope-race',
  'logout-race',
  'legacy-preference',
  'visual-banco',
  'visual-plano',
  'visual-ritmo',
  'visual-noche',
] as const
type Case = (typeof CASES)[number]
const OWNER = 'e2e-branding-owner'
const SCOPED = 'e2e-branding-scoped'
const HEADERS = { 'X-OCWP-Write-Protocol': '1' }
const THEMES = [
  { id: 'banco', label: 'Banco de trabajo', palette: 'arcilla' },
  { id: 'plano', label: 'Plano técnico', palette: 'cobalto' },
  { id: 'ritmo', label: 'Ritmo modular', palette: 'frambuesa' },
  { id: 'noche', label: 'Turno nocturno', palette: 'lima' },
] as const

function fixture(name: Case, info: TestInfo) {
  expect(info.retry).toBeLessThan(2)
  const base = 20000 + info.retry * 1000 + CASES.indexOf(name) * 10
  const id = (entity: number) =>
    `00000000-0000-7000-8000-${String(base + entity).padStart(12, '0')}`
  return {
    organizationId: id(0),
    locationA: id(1),
    locationB: id(2),
    ownerId: id(3),
    scopedId: id(4),
  }
}
type Fixture = ReturnType<typeof fixture>
function endpoint(locationId: string) {
  return `/api/v1/locations/${locationId}/branding`
}
async function token(request: APIRequestContext, f: Fixture, username = OWNER) {
  const response = await request.post('/api/v1/auth/login', {
    data: { organization_id: f.organizationId, username, password: PASSWORD },
  })
  expect(response.status()).toBe(200)
  return ((await response.json()) as { access_token: string }).access_token
}
function authorization(accessToken: string) {
  return { ...HEADERS, Authorization: `Bearer ${accessToken}` }
}
async function read(request: APIRequestContext, accessToken: string, location: string) {
  const response = await request.get(endpoint(location), { headers: authorization(accessToken) })
  expect(response.status()).toBe(200)
  expect(response.headers()['cache-control']).toContain('no-store')
  return (await response.json()) as BrandingProfile
}
async function put(
  request: APIRequestContext,
  accessToken: string,
  location: string,
  input: BrandingPutRequest,
) {
  const response = await request.put(endpoint(location), {
    headers: authorization(accessToken),
    data: input,
  })
  expect(response.status()).toBe(200)
  expect(response.headers()['cache-control']).toContain('no-store')
  return (await response.json()) as BrandingProfile
}
function input(
  name: string,
  palette: BrandingPutRequest['palette_id'] = 'jade',
  version = 0,
  logo: string | null = null,
): BrandingPutRequest {
  return {
    expected_version: version,
    display_name: name,
    palette_id: palette,
    logo_png_base64: logo,
  }
}
async function login(page: Page, f: Fixture, username = OWNER, operational = true) {
  await page.goto('/')
  await page.getByLabel('Organización', { exact: true }).fill(f.organizationId)
  await page.getByLabel('Usuario', { exact: true }).fill(username)
  await page.getByLabel('Contraseña', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click()
  await expect(
    page.locator('[data-runtime-state="SELECTOR"], [data-runtime-state="READY"]'),
  ).toBeVisible({ timeout: 20_000 })
  if (operational) {
    if (username === OWNER)
      await page.getByRole('button', { name: 'Taller marca A', exact: true }).click()
    await waitForReady(page)
  }
}
async function openBranding(page: Page) {
  const navigation = page.getByRole('link', { name: 'Administración', exact: true })
  if (await navigation.isVisible()) await navigation.click()
  const verify = page.getByRole('button', {
    name: 'Verificar acceso a administración',
    exact: true,
  })
  const session = page.getByRole('heading', { name: 'Mi sesión', exact: true })
  await expect(verify.or(session)).toBeVisible()
  // Technical accounts can publish SELECTOR while automatic verification is
  // still running. Its disabled button is replaced by the admitted session;
  // wait for either actionable state, not for that transient button to enable.
  await expect
    .poll(
      async () =>
        (await session.isVisible()) || (await verify.and(page.locator(':enabled')).isVisible()),
    )
    .toBe(true)
  if (!(await session.isVisible())) await verify.click()
  await expect(session).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Marca compartida del taller', exact: true }),
  ).toBeVisible()
}
async function loadEditor(page: Page, location?: string) {
  await openBranding(page)
  if (location) await page.getByLabel('Taller objetivo', { exact: true }).fill(location)
  await page.getByRole('button', { name: 'Cargar marca y revisar versión', exact: true }).click()
  await expect(
    page.getByRole('form', { name: 'Editar marca compartida', exact: true }),
  ).toBeVisible()
}
async function openSettings(page: Page) {
  await page.getByRole('button', { name: 'Personalización', exact: true }).click()
  await expect(page.getByRole('radio', { name: /Banco de trabajo/ })).toBeEnabled()
}
async function refresh(page: Page) {
  await openSettings(page)
  await page.getByRole('button', { name: 'Actualizar marca compartida', exact: true }).click()
  await page.getByRole('button', { name: 'Cerrar personalización', exact: true }).click()
}
async function expectBrand(page: Page, profile: BrandingProfile) {
  await expect(page.locator('.workshop-identity')).toHaveAccessibleName(
    `${profile.display_name}, taller activo`,
  )
  if (profile.logo_state === 'available') {
    await expect(page.locator('.workshop-logo')).toHaveAttribute(
      'src',
      `data:image/png;base64,${profile.logo!.png_base64}`,
    )
    await expect
      .poll(() =>
        page.locator('.workshop-logo').evaluate((element) => {
          const image = element as HTMLImageElement
          return image.complete && image.naturalWidth > 0
        }),
      )
      .toBe(true)
  }
}
async function rows<T>(page: Page, store: string): Promise<T[]> {
  return page.evaluate(
    async ({ name, store }) => {
      const open = indexedDB.open(name)
      open.onupgradeneeded = () => open.transaction!.abort()
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        open.onsuccess = () => resolve(open.result)
        open.onerror = () => reject(open.error)
      })
      try {
        const request = db.transaction(store, 'readonly').objectStore(store).getAll()
        return await new Promise<T[]>((resolve, reject) => {
          request.onsuccess = () => resolve(request.result as T[])
          request.onerror = () => reject(request.error)
        })
      } finally {
        db.close()
      }
    },
    { name: DATABASE, store },
  )
}
async function syntheticLogo(page: Page, tone: 'dark' | 'light' | 'bright' = 'bright') {
  // Generated test artwork only. Transparent pixels and a recognisable bicycle
  // exercise actual decoding/scaling on both surface schemes, not a 1px stand-in.
  return page.evaluate((tone) => {
    const canvas = document.createElement('canvas')
    canvas.width = 240
    canvas.height = 80
    const context = canvas.getContext('2d')!
    context.strokeStyle = tone === 'light' ? '#f4faf5' : tone === 'dark' ? '#183c32' : '#d24535'
    context.fillStyle = context.strokeStyle
    context.lineWidth = 4
    for (const x of [27, 85]) {
      context.beginPath()
      context.arc(x, 52, 20, 0, 2 * Math.PI)
      context.stroke()
    }
    context.beginPath()
    context.moveTo(27, 52)
    context.lineTo(47, 23)
    context.lineTo(65, 52)
    context.lineTo(27, 52)
    context.lineTo(72, 27)
    context.lineTo(85, 52)
    context.stroke()
    context.beginPath()
    context.moveTo(39, 22)
    context.lineTo(54, 22)
    context.moveTo(72, 27)
    context.lineTo(68, 12)
    context.lineTo(81, 12)
    context.stroke()
    context.font = 'bold 19px sans-serif'
    context.fillText('TALLER', 115, 37)
    context.font = '16px sans-serif'
    context.fillText('E2E', 115, 59)
    if (context.getImageData(0, 0, 1, 1).data[3] !== 0)
      throw new Error('Fixture must be transparent')
    return canvas.toDataURL('image/png').slice('data:image/png;base64,'.length)
  }, tone)
}
type LogoTone = 'dark' | 'light' | 'bright'
async function expectLogoCanvas(image: Locator, tone: LogoTone, source?: string) {
  const backing = tone === 'light' ? 'dark' : 'light'
  await expect(image).toHaveAttribute('data-logo-backing', backing)
  await expect(image).toHaveCSS(
    'background-color',
    backing === 'dark' ? 'rgb(32, 32, 32)' : 'rgb(255, 255, 255)',
  )
  await expect(image).toHaveCSS('forced-color-adjust', 'none')
  await expect(image).toHaveCSS('filter', 'none')
  if (source) await expect(image).toHaveAttribute('src', source)
  const contrast = await image.evaluate((element, tone) => {
    const ink = tone === 'light' ? [244, 250, 245] : tone === 'dark' ? [24, 60, 50] : [210, 69, 53]
    const plate = getComputedStyle(element).backgroundColor.match(/\d+/g)!.slice(0, 3).map(Number)
    const luminance = (rgb: number[]) =>
      rgb
        .map((byte) => byte / 255)
        .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i]!, 0)
    const a = luminance(ink),
      b = luminance(plate)
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
  }, tone)
  expect(
    contrast,
    'known synthetic opaque ink versus the browser-used plate',
  ).toBeGreaterThanOrEqual(4.5)
}

async function expectSaveWords(page: Page, info: TestInfo, label: string) {
  const save = page.getByRole('button', { name: 'Guardar marca compartida', exact: true })
  const geometry = await save.evaluate((element) => {
    const rect = element.getBoundingClientRect(),
      style = getComputedStyle(element)
    const zoom = Number(getComputedStyle(document.documentElement).zoom)
    const words = []
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      for (const word of (node.textContent ?? '').matchAll(/\S+/g)) {
        const range = document.createRange()
        range.setStart(node, word.index)
        range.setEnd(node, word.index + word[0].length)
        words.push({
          text: word[0],
          fragments: Array.from(range.getClientRects(), (r) => ({ left: r.left, right: r.right })),
        })
      }
    }
    const form = element.closest('form')!.getBoundingClientRect()
    return {
      text: element.textContent,
      words,
      visibility: style.visibility,
      opacity: Number(style.opacity),
      left: rect.left,
      right: rect.right,
      formLeft: form.left,
      formRight: form.right,
      contentLeft:
        rect.left + zoom * (parseFloat(style.paddingLeft) + parseFloat(style.borderLeftWidth)),
      contentRight:
        rect.right - zoom * (parseFloat(style.paddingRight) + parseFloat(style.borderRightWidth)),
      width: rect.width / zoom,
      height: rect.height / zoom,
      viewport: window.innerWidth,
    }
  })
  await info.attach(`save-word-geometry-${label}`, {
    body: JSON.stringify(geometry),
    contentType: 'application/json',
  })
  expect(geometry.text).toBe('Guardar marca compartida')
  expect(geometry.words.map((word) => word.text)).toEqual(['Guardar', 'marca', 'compartida'])
  expect(geometry.visibility).toBe('visible')
  expect(geometry.opacity).toBe(1)
  expect(geometry.width).toBeGreaterThanOrEqual(56)
  expect(geometry.height).toBeGreaterThanOrEqual(56)
  expect(geometry.left).toBeGreaterThanOrEqual(Math.max(0, geometry.formLeft))
  expect(geometry.right).toBeLessThanOrEqual(Math.min(geometry.viewport, geometry.formRight))
  for (const word of geometry.words) {
    expect(word.fragments, `intact save word: ${word.text}`).toHaveLength(1)
    expect(word.fragments[0]!.left).toBeGreaterThanOrEqual(geometry.contentLeft - 0.5)
    expect(word.fragments[0]!.right).toBeLessThanOrEqual(geometry.contentRight + 0.5)
  }
}

async function captureLogo(image: Locator, info: TestInfo, name: string) {
  const path = info.outputPath(`${name}.png`)
  await image.screenshot({ path })
  await info.attach(name, { path, contentType: 'image/png' })
}

async function capture(page: Page, info: TestInfo, name: string) {
  expect(
    await page
      .locator('input[type="password"]')
      .evaluateAll((inputs) => inputs.every((input) => (input as HTMLInputElement).value === '')),
  ).toBe(true)
  // Trigger lazy content visibility without changing focus or values.
  await page.evaluate(() => {
    for (const node of document.querySelectorAll<HTMLElement>('[style], section, article')) {
      if (getComputedStyle(node).contentVisibility === 'auto')
        node.style.contentVisibility = 'visible'
    }
    window.scrollTo(0, 0)
  })
  const path = info.outputPath(`${name}.png`)
  await page.screenshot({ path, fullPage: true })
  await info.attach(name, { path, contentType: 'image/png' })
}

// Genuine UI -> FastAPI -> PostgreSQL, two contexts/users, no mocked profiles.
test('per-location brands converge to a second user without changing operational scope', async ({
  page,
  browser,
  request,
}, info) => {
  const f = fixture('convergence', info)
  const owner = await token(request, f)
  const original = await put(request, owner, f.locationA, input('Marca A inicial', 'jade'))
  await put(request, owner, f.locationB, input('Marca B independiente', 'cobalto'))
  await login(page, f)
  await expectBrand(page, original)
  const before = await kernelSnapshot(page)
  const second = await browser.newContext()
  try {
    const observer = await second.newPage()
    await login(observer, f, SCOPED)
    await expectBrand(observer, original)
    const logo = await syntheticLogo(page)
    await loadEditor(page, f.locationA)
    await page.getByLabel('Nombre visible del taller', { exact: true }).fill('Marca A compartida')
    await page
      .getByRole('combobox', { name: 'Paleta compartida', exact: true })
      .selectOption('arcilla')
    // Native File/DataTransfer inputs contain only our generated synthetic PNG.
    await page
      .getByLabel('Archivo para logo compartido', { exact: true })
      .evaluate((element, encoded) => {
        const file = new File(
          [Uint8Array.from(atob(encoded), (byte) => byte.charCodeAt(0))],
          'synthetic-transparent.png',
          { type: 'image/png' },
        )
        const transfer = new DataTransfer()
        transfer.items.add(file)
        ;(element as HTMLInputElement).files = transfer.files
        element.dispatchEvent(new Event('change', { bubbles: true }))
      }, logo)
    await expect(
      page
        .getByRole('status')
        .filter({ hasText: 'Vista previa lista. El logo solo se comparte al guardar.' }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Guardar marca compartida', exact: true }).click()
    await expect(
      page.getByRole('status').filter({ hasText: 'Marca compartida guardada.' }),
    ).toBeVisible()
    const saved = await read(request, owner, f.locationA)
    expect(saved.version).toBe(2)
    expect(saved.logo_state).toBe('available')
    await expectBrand(page, saved)
    await refresh(observer)
    await expectBrand(observer, saved)
    const observerRows = await rows<BrandingSnapshot>(observer, 'brandingSnapshots')
    expect(observerRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ userId: f.scopedId, locationId: f.locationA, version: 2 }),
      ]),
    )
    await loadEditor(page, f.locationB)
    await page.getByLabel('Nombre visible del taller', { exact: true }).fill('Marca B revisada')
    await page.getByRole('button', { name: 'Guardar marca compartida', exact: true }).click()
    await expect(
      page.getByRole('status').filter({ hasText: 'Marca compartida guardada.' }),
    ).toBeVisible()
    await expectBrand(page, saved)
    expect((await read(request, owner, f.locationB)).display_name).toBe('Marca B revisada')
    const after = await kernelSnapshot(page)
    expect(after.context.selectedLocationId).toBe(f.locationA)
    expect(after.partition.partitionId).toBe(before.partition.partitionId)
    expect(after.journal).toEqual(before.journal)
    expect((await read(request, owner, f.locationA)).version).toBe(2)
  } finally {
    await second.close()
  }
})

test('verified brand survives offline reload while shared edits never enter the journal', async ({
  browser,
  request,
}, info) => {
  const f = fixture('offline', info)
  const owner = await token(request, f)
  let version = 0
  for (const tone of ['dark', 'light', 'bright'] as const) {
    // Independent disposable contexts keep each pending journal intact and
    // offline. No reconnect/ACK from a previous artwork can race these checks.
    const context = await browser.newContext()
    const page = await context.newPage()
    try {
      await login(page, f)
      let writes = 0
      page.on('request', (r) => {
        if (r.url().endsWith('/branding') && r.method() === 'PUT') writes++
      })
      const saved = await put(
        request,
        owner,
        f.locationA,
        input('Marca disponible sin conexión', 'jade', version, await syntheticLogo(page, tone)),
      )
      version = saved.version
      await refresh(page)
      await expectBrand(page, saved)
      await page.evaluate(async () => {
        await navigator.serviceWorker.ready
      })
      await loadEditor(page, f.locationA)
      await page
        .getByLabel('Nombre visible del taller', { exact: true })
        .fill('Borrador compartido sin enviar')
      await page.context().setOffline(true)
      await expect(page.getByLabel('Estado de sincronización')).toContainText('Sin conexión')
      await expect(
        page.getByRole('button', { name: 'Guardar marca compartida', exact: true }),
      ).toHaveCount(0)
      const operation = await createCustomer(
        page,
        `Cliente pendiente preservado durante marca offline ${tone}`,
      )
      const before = await kernelSnapshot(page)
      for (const scheme of ['light', 'dark'] as const) {
        await openSettings(page)
        await expect(
          page.getByText('Copia verificada disponible sin conexión.', { exact: false }),
        ).toBeVisible()
        await page
          .getByRole('combobox', { name: 'Esquema de superficies', exact: true })
          .selectOption(scheme)
        await page.getByRole('button', { name: 'Cerrar personalización', exact: true }).click()
        await page.reload({ waitUntil: 'domcontentloaded' })
        await waitForReady(page)
        await expectBrand(page, saved)
        await expect(page.locator('.workshop-shell')).toHaveAttribute('data-scheme', scheme)
        for (const forcedColors of ['none', 'active'] as const) {
          await page.emulateMedia({ forcedColors })
          await expectLogoCanvas(
            page.locator('.workshop-logo'),
            tone,
            `data:image/png;base64,${saved.logo!.png_base64}`,
          )
          await captureLogo(
            page.locator('.workshop-logo'),
            info,
            `logo-offline-${tone}-${scheme}-${forcedColors}`,
          )
        }
        await page.emulateMedia({ forcedColors: 'none' })
        const after = await kernelSnapshot(page)
        expect(after.journal).toEqual(before.journal)
        expect(after.journal).toContainEqual(operation)
        expect(after.delivery).toEqual(before.delivery)
        expect(writes).toBe(0)
        expect((await read(request, owner, f.locationA)).version).toBe(version)
      }
    } finally {
      await context.close()
    }
  }
})

const GRANTS = [
  { key: 'none', read: false, write: false },
  { key: 'legacy', read: false, write: false },
  { key: 'read', read: true, write: false },
  { key: 'write', read: false, write: true },
  { key: 'legacy-read', read: true, write: false },
  { key: 'legacy-write', read: false, write: true },
  { key: 'both', read: true, write: true },
  { key: 'concrete-old', read: false, write: false },
  { key: 'technical', read: false, write: false },
] as const
for (const grant of GRANTS) {
  test(`explicit grants ${grant.key}: read/write UI and API stay separate and location scoped`, async ({
    page,
    request,
  }, info) => {
    const f = fixture(`grants-${grant.key}`, info)
    const owner = await token(request, f)
    const saved = await put(request, owner, f.locationA, input('Marca restringida del taller A'))
    const scoped = await token(request, f, SCOPED)
    const get = await request.get(endpoint(f.locationA), { headers: authorization(scoped) })
    expect(get.status()).toBe(grant.read ? 200 : 403)
    await login(page, f, SCOPED, grant.key !== 'technical')
    await openBranding(page)
    if (grant.read) {
      await expectBrand(page, saved)
      await loadEditor(page)
      if (!grant.write)
        await expect(page.getByLabel('Nombre visible del taller', { exact: true })).toBeDisabled()
      else await expect(page.getByLabel('Nombre visible del taller', { exact: true })).toBeEnabled()
    } else if (grant.write) {
      await expect(page.locator('.workshop-identity')).not.toHaveAccessibleName(
        `${saved.display_name}, taller activo`,
      )
      await expect(
        page.getByRole('button', { name: 'Cargar marca y revisar versión', exact: true }),
      ).toHaveCount(0)
      await page
        .getByRole('button', { name: 'Preparar reemplazo sin lectura', exact: true })
        .click()
      await expect(page.getByLabel('Nombre visible del taller', { exact: true })).toHaveValue('')
      await expect(page.getByLabel('Versión esperada', { exact: true })).toHaveValue('0')
    } else {
      await expect(
        page.getByText('Tu cuenta no tiene permisos explícitos de marca compartida.', {
          exact: false,
        }),
      ).toBeVisible()
      await expect(
        page.getByRole('form', { name: 'Editar marca compartida', exact: true }),
      ).toHaveCount(0)
    }
    const update = await request.put(endpoint(f.locationA), {
      headers: authorization(scoped),
      data: input('Reemplazo autorizado si tiene escritura', 'arcilla', 1),
    })
    expect(update.status()).toBe(grant.write ? 200 : 403)
    for (const method of ['get', 'put'] as const) {
      const response =
        method === 'get'
          ? await request.get(endpoint(f.locationB), { headers: authorization(scoped) })
          : await request.put(endpoint(f.locationB), {
              headers: authorization(scoped),
              data: input('No debe guardarse'),
            })
      expect(response.status()).toBe(403)
    }
    if (grant.key !== 'technical') {
      const snapshot = await kernelSnapshot(page)
      expect(snapshot.context.capabilities.includes('branding.read')).toBe(grant.read)
      expect(snapshot.context.capabilities.includes('branding.write')).toBe(grant.write)
      const cached = await rows<BrandingSnapshot>(page, 'brandingSnapshots')
      expect(cached.some((row) => row.userId === f.scopedId)).toBe(grant.read)
      expect(snapshot.journal).toEqual([])
    }
    expect((await read(request, owner, f.locationB)).version).toBe(0)
  })
}

test('CAS conflict preserves the immutable reviewed version and unsent branding draft', async ({
  page,
  request,
}, info) => {
  const f = fixture('conflict', info),
    owner = await token(request, f)
  await put(request, owner, f.locationA, input('Primera versión'))
  await login(page, f)
  await loadEditor(page, f.locationA)
  await page
    .getByLabel('Nombre visible del taller', { exact: true })
    .fill('Borrador que requiere revisión')
  await put(request, owner, f.locationA, input('Cambio de otro dispositivo', 'arcilla', 1))
  const sentVersions: number[] = []
  page.on('request', (r) => {
    if (r.url().endsWith('/branding') && r.method() === 'PUT')
      sentVersions.push((r.postDataJSON() as BrandingPutRequest).expected_version)
  })
  await page.getByRole('button', { name: 'Guardar marca compartida', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('La marca cambió. Tu borrador se conserva')
  const form = page.getByRole('form', { name: 'Editar marca compartida', exact: true })
  await expect(form).toHaveAttribute('data-dirty', 'true')
  await expect(form.getByLabel('Nombre visible del taller', { exact: true })).toHaveValue(
    'Borrador que requiere revisión',
  )
  await expect(form).toContainText('Versión revisada: 1.')
  expect(sentVersions).toEqual([1])
  expect((await read(request, owner, f.locationA)).version).toBe(2)
  const dialog = page.waitForEvent('dialog')
  const reload = page
    .getByRole('button', { name: 'Cargar marca y revisar versión', exact: true })
    .click()
  const confirmation = await dialog
  expect(confirmation.message()).toContain('¿Descartar el borrador de marca compartida?')
  await confirmation.accept()
  await reload
  await expect(form.getByLabel('Nombre visible del taller', { exact: true })).toHaveValue(
    'Cambio de otro dispositivo',
  )
  await expect(form).toContainText('Versión revisada: 2.')
  expect((await kernelSnapshot(page)).journal).toEqual([])
})

test('lost committed response stays unconfirmed with draft retained and no automatic replay', async ({
  page,
  request,
}, info) => {
  const f = fixture('unconfirmed', info),
    owner = await token(request, f)
  await put(request, owner, f.locationA, input('Antes del resultado incierto'))
  await login(page, f)
  await loadEditor(page, f.locationA)
  await page
    .getByLabel('Nombre visible del taller', { exact: true })
    .fill('Guardado cuya respuesta se pierde')
  let writes = 0
  await page.route(`**${endpoint(f.locationA)}`, async (route) => {
    if (route.request().method() !== 'PUT') {
      await route.continue()
      return
    }
    writes++
    const committed = await route.fetch()
    expect(committed.status()).toBe(200)
    await route.abort('failed')
  })
  await page.getByRole('button', { name: 'Guardar marca compartida', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText(
    'Resultado sin confirmar. Tu borrador se conserva',
  )
  await expect(page.getByLabel('Nombre visible del taller', { exact: true })).toHaveValue(
    'Guardado cuya respuesta se pierde',
  )
  await expect(
    page.getByRole('form', { name: 'Editar marca compartida', exact: true }),
  ).toContainText('Versión revisada: 1.')
  expect((await read(request, owner, f.locationA)).version).toBe(2)
  await refresh(page)
  await expect(page.getByRole('alert')).toContainText('Resultado sin confirmar')
  expect(writes).toBe(1)
  expect((await kernelSnapshot(page)).journal).toEqual([])
})

for (const transition of ['scope', 'logout'] as const) {
  test(`late branding response after ${transition} cannot republish an obsolete scope or session`, async ({
    page,
    request,
  }, info) => {
    const f = fixture(`${transition}-race`, info),
      owner = await token(request, f)
    await put(request, owner, f.locationA, input('Marca A antes de la carrera'))
    const other = await put(request, owner, f.locationB, input('Marca B vigente', 'cobalto'))
    await login(page, f)
    await expect(page.locator('.workshop-identity')).toHaveAccessibleName(
      'Marca A antes de la carrera, taller activo',
    )
    await put(request, owner, f.locationA, input('Respuesta antigua retenida', 'arcilla', 1))
    let release = () => {},
      held = false,
      once = true
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route(`**${endpoint(f.locationA)}`, async (route) => {
      if (!once || route.request().method() !== 'GET') {
        await route.continue()
        return
      }
      once = false
      const response = await route.fetch()
      expect(response.status()).toBe(200)
      expect((await response.json()).version).toBe(2)
      held = true
      await gate
      await route.fulfill({ response })
    })
    try {
      await refresh(page)
      await expect.poll(() => held).toBe(true)
      if (transition === 'scope') {
        await page.getByRole('button', { name: 'Cambiar taller', exact: true }).click()
        await expect(page.locator('.workshop-identity')).toHaveCount(0)
        await page.getByRole('button', { name: 'Taller marca B', exact: true }).click()
        await waitForReady(page)
        await expectBrand(page, other)
      } else {
        await page.getByRole('button', { name: 'Cerrar esta sesión', exact: true }).click()
        await expect(
          page.getByRole('button', { name: 'Iniciar sesión', exact: true }),
        ).toBeVisible()
        await expect(page.locator('.workshop-identity')).toHaveCount(0)
        const current = await put(
          request,
          owner,
          f.locationA,
          input('Nueva sesión y versión actual', 'lima', 2),
        )
        await login(page, f)
        await expectBrand(page, current)
      }
      release()
      await page.unrouteAll({ behavior: 'wait' })
      const after = await kernelSnapshot(page)
      expect(after.context.selectedLocationId).toBe(
        transition === 'scope' ? f.locationB : f.locationA,
      )
      await expect(page.locator('.workshop-identity')).not.toHaveAccessibleName(
        'Respuesta antigua retenida, taller activo',
      )
      const snapshots = await rows<BrandingSnapshot>(page, 'brandingSnapshots')
      expect(
        snapshots.some(
          (snapshot) => snapshot.profile.display_name === 'Respuesta antigua retenida',
        ),
      ).toBe(false)
      expect(after.journal).toEqual([])
    } finally {
      release()
      await page.unrouteAll({ behavior: 'wait' })
    }
  })
}

test('persisted v1 personal palette and local logo survive reads until explicit workshop inheritance', async ({
  page,
  request,
}, info) => {
  const f = fixture('legacy-preference', info),
    owner = await token(request, f)
  await login(page, f)
  const shared = await put(
    request,
    owner,
    f.locationA,
    input('Taller con herencia explícita', 'jade', 0, await syntheticLogo(page, 'bright')),
  )
  await refresh(page)
  await expectBrand(page, shared)
  const localLogo = `data:image/png;base64,${await syntheticLogo(page, 'dark')}`
  const appearance = {
    key: JSON.stringify(['appearance', f.organizationId, f.ownerId]),
    organizationId: f.organizationId,
    userId: f.ownerId,
    locationId: null,
    kind: 'appearance',
    value: {
      schemaVersion: 1,
      themeId: 'noche',
      paletteId: 'bosque',
      scheme: 'light',
      density: 'workshop',
      logoDataUrl: null,
    },
  }
  const logo = {
    key: JSON.stringify(['logo', f.organizationId, f.ownerId, f.locationA]),
    organizationId: f.organizationId,
    userId: f.ownerId,
    locationId: f.locationA,
    kind: 'logo',
    value: localLogo,
  }
  // Synthetic pre-existing v1 records in an already admitted native database.
  // First-admission legacy copying and native60->70 are separate native cases.
  await page.evaluate(
    async ({ name, records }) => {
      const open = indexedDB.open(name)
      open.onupgradeneeded = () => open.transaction!.abort()
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        open.onsuccess = () => resolve(open.result)
        open.onerror = () => reject(open.error)
      })
      try {
        const tx = db.transaction('presentationPreferences', 'readwrite')
        for (const record of records) tx.objectStore('presentationPreferences').put(record)
        await new Promise<void>((resolve, reject) => {
          tx.oncomplete = () => resolve()
          tx.onabort = () => reject(tx.error)
        })
      } finally {
        db.close()
      }
    },
    { name: DATABASE, records: [appearance, logo] },
  )
  let uploads = 0
  page.on('request', (r) => {
    if (r.url().endsWith('/branding') && r.method() === 'PUT') uploads++
  })
  await page.reload()
  await waitForReady(page)
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', 'noche')
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-scheme', 'light')
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-density', 'workshop')
  await expect(page.locator('.workshop-logo')).toHaveAttribute('src', localLogo)
  const original = await rows(page, 'presentationPreferences')
  expect(original).toEqual(expect.arrayContaining([appearance, logo]))
  await openSettings(page)
  await expect(page.getByText('Colores: Selección personal.', { exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Paleta personal', exact: true })).toHaveValue(
    'bosque',
  )
  await page.getByRole('button', { name: 'Usar colores del taller', exact: true }).click()
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  await expect(
    page.getByText('Colores: Heredados del taller activo.', { exact: true }),
  ).toBeVisible()
  await expect(page.locator('.workshop-logo')).toHaveAttribute('src', localLogo)
  await page.getByRole('button', { name: 'Restablecer mi apariencia', exact: true }).click()
  await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', 'banco')
  await expect(page.locator('.workshop-logo')).toHaveAttribute('src', localLogo)
  expect(
    (await rows<{ kind: string; value: unknown }>(page, 'presentationPreferences')).find(
      (row) => row.kind === 'logo',
    ),
  ).toEqual(logo)
  await page.getByRole('button', { name: 'Usar logo del taller', exact: true }).click()
  await expectBrand(page, shared)
  await page.getByRole('button', { name: 'Quitar logo de mi vista', exact: true }).click()
  await expect(page.locator('.workshop-logo')).toHaveCount(0)
  await expect(page.locator('.preference-status')).toContainText('guardada en este dispositivo')
  await page.reload()
  await waitForReady(page)
  await expect(page.locator('.workshop-logo')).toHaveCount(0)
  await openSettings(page)
  for (const tone of ['dark', 'light', 'bright'] as const) {
    const encoded = await syntheticLogo(page, tone)
    await page.getByLabel('Archivo de logo local', { exact: true }).evaluate((element, encoded) => {
      const file = new File(
        [Uint8Array.from(atob(encoded), (byte) => byte.charCodeAt(0))],
        'synthetic-personal.png',
        { type: 'image/png' },
      )
      const transfer = new DataTransfer()
      transfer.items.add(file)
      ;(element as HTMLInputElement).files = transfer.files
      element.dispatchEvent(new Event('change', { bubbles: true }))
    }, encoded)
    const preview = page.getByRole('img', { name: 'Vista previa del logo local', exact: true })
    await expect(preview).toBeVisible()
    const preparedSource = (await preview.getAttribute('src'))!
    for (const scheme of ['light', 'dark'] as const) {
      await page
        .getByRole('combobox', { name: 'Esquema de superficies', exact: true })
        .selectOption(scheme)
      for (const forcedColors of ['none', 'active'] as const) {
        await page.emulateMedia({ forcedColors })
        await expectLogoCanvas(preview, tone, preparedSource)
      }
    }
    await captureLogo(preview, info, `logo-personal-preview-${tone}-forced-colors`)
    await page.emulateMedia({ forcedColors: 'none' })
    await page.getByRole('button', { name: 'Descartar vista previa', exact: true }).click()
    await expect(preview).toHaveCount(0)
    await expect(page.locator('.workshop-logo')).toHaveCount(0)
  }
  expect(uploads).toBe(0)
  expect((await read(request, owner, f.locationA)).version).toBe(1)
  expect((await kernelSnapshot(page)).journal).toEqual([])
})

for (const theme of THEMES) {
  test(`visual ${theme.id}: transparent light/dark branding, responsive controls and operational draft stability`, async ({
    page,
    request,
  }, info) => {
    test.setTimeout(120_000)
    const f = fixture(`visual-${theme.id}`, info),
      owner = await token(request, f)
    await page.setViewportSize({ width: 1440, height: 1000 })
    await login(page, f)
    const before = await kernelSnapshot(page)
    const operational = page.getByLabel('Nombre', { exact: true })
    const draft = 'Borrador operativo que no se remonta'
    await operational.fill(draft)
    await operational.evaluate((element) => (element as HTMLInputElement).setSelectionRange(3, 11))
    const node = await operational.elementHandle()
    await openSettings(page)
    const choice = page.getByRole('radio', { name: new RegExp(theme.label) })
    await choice.focus()
    await choice.press('Space')
    await expect(choice).toBeChecked()
    await expect(choice).toBeFocused()
    await page.getByLabel('Modo taller', { exact: false }).check()
    await choice.press('Escape')
    await expect(page.getByRole('button', { name: 'Personalización', exact: true })).toBeFocused()
    expect(await node!.evaluate((element) => element.isConnected)).toBe(true)
    await expect(operational).toHaveValue(draft)
    expect(
      await operational.evaluate((element) => (element as HTMLInputElement).selectionStart),
    ).toBe(3)
    let version = 0
    for (const scheme of ['light', 'dark'] as const) {
      await openSettings(page)
      await page
        .getByRole('combobox', { name: 'Esquema de superficies', exact: true })
        .selectOption(scheme)
      await page.getByRole('button', { name: 'Cerrar personalización', exact: true }).click()
      const saved = await put(
        request,
        owner,
        f.locationA,
        input(
          `Taller E2E ${theme.label} ${scheme === 'light' ? 'claro' : 'oscuro'}`,
          theme.palette,
          version,
          await syntheticLogo(page, scheme === 'light' ? 'dark' : 'light'),
        ),
      )
      version = saved.version
      // Deliver the real saved profile while the operational input owns focus.
      // The response is delayed, never replaced, so re-render node identity is tested.
      let release = () => {},
        held = false
      const gate = new Promise<void>((resolve) => {
        release = resolve
      })
      await page.route(`**${endpoint(f.locationA)}`, async (route) => {
        const response = await route.fetch()
        expect(response.status()).toBe(200)
        held = true
        await gate
        await route.fulfill({ response })
      })
      try {
        await refresh(page)
        await expect.poll(() => held).toBe(true)
        await operational.focus()
        await operational.evaluate((element) =>
          (element as HTMLInputElement).setSelectionRange(3, 11),
        )
        release()
        await expectBrand(page, saved)
        await expect(operational).toBeFocused()
        expect(await node!.evaluate((element) => element.isConnected)).toBe(true)
        await expect(operational).toHaveValue(draft)
        expect(
          await operational.evaluate((element) => (element as HTMLInputElement).selectionStart),
        ).toBe(3)
      } finally {
        release()
        await page.unrouteAll({ behavior: 'wait' })
      }
      await loadEditor(page, f.locationA)
      await expect(
        page.getByRole('combobox', { name: 'Paleta compartida', exact: true }),
      ).toHaveValue(theme.palette)
      await expect(page.locator('.workshop-shell')).toHaveAttribute('data-theme', theme.id)
      await expect(page.locator('.workshop-shell')).toHaveAttribute('data-scheme', scheme)
      const palette = PALETTES.find((item) => item.id === theme.palette)!
      expect(
        await page
          .locator('.workshop-shell')
          .evaluate((element) => element.style.getPropertyValue('--ocwp-color-accent')),
      ).toBe(palette[scheme].primary)
      for (const [size, width] of [
        ['desktop', 1440],
        ['tablet', 834],
        ['mobile', 320],
      ] as const) {
        await page.setViewportSize({ width, height: 1000 })
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        ).toBe(true)
        for (const control of [
          page.getByLabel('Nombre visible del taller', { exact: true }),
          page.getByRole('combobox', { name: 'Paleta compartida', exact: true }),
        ]) {
          const box = await control.boundingBox()
          expect(box!.height).toBeGreaterThanOrEqual(48)
          expect(box!.width).toBeGreaterThanOrEqual(48)
        }
        const save = page.getByRole('button', { name: 'Guardar marca compartida', exact: true })
        expect((await save.boundingBox())!.height).toBeGreaterThanOrEqual(56)
        await expectSaveWords(page, info, `${theme.id}-${scheme}-${width}`)
        await expectLogoCanvas(
          page.locator('.workshop-logo'),
          scheme === 'light' ? 'dark' : 'light',
        )
        await expectLogoCanvas(
          page.locator('.branding-preview'),
          scheme === 'light' ? 'dark' : 'light',
        )
        const accessibility = await new AxeBuilder({ page }).analyze()
        expect(
          accessibility.violations.filter((violation) =>
            ['critical', 'serious'].includes(violation.impact ?? ''),
          ),
        ).toEqual([])
        expect(await node!.evaluate((element) => element.isConnected)).toBe(true)
        await expect(operational).toHaveValue(draft)
        await capture(page, info, `branding-${theme.id}-${scheme}-transparent-${size}-${width}`)
      }
      // 640 viewport / 200% CSS enlargement = 320 effective CSS px. This is
      // labelled CSS enlargement, never physical browser/device zoom evidence.
      await page.setViewportSize({ width: 640, height: 1000 })
      await page.evaluate(() => {
        document.documentElement.style.zoom = '2'
      })
      expect(
        await page.evaluate(() => ({
          effectiveCssWidth:
            window.innerWidth / Number(getComputedStyle(document.documentElement).zoom),
          noOverflow: document.documentElement.scrollWidth <= window.innerWidth,
        })),
      ).toEqual({ effectiveCssWidth: 320, noOverflow: true })
      await expectSaveWords(page, info, `${theme.id}-${scheme}-css200`)
      await capture(page, info, `branding-${theme.id}-${scheme}-css-enlargement-200-percent`)
      await page.evaluate(() => {
        document.documentElement.style.zoom = '1'
      })
      await page.setViewportSize({ width: 320, height: 1000 })
      // Both artwork polarities plus the existing red asset use the same plate
      // in either surface scheme. The base full-page matrix above is retained.
      for (const tone of ['dark', 'light', 'bright'] as const) {
        const artwork = await put(
          request,
          owner,
          f.locationA,
          input(saved.display_name, theme.palette, version, await syntheticLogo(page, tone)),
        )
        version = artwork.version
        await refresh(page)
        await expectBrand(page, artwork)
        await loadEditor(page, f.locationA)
        for (const forcedColors of ['none', 'active'] as const) {
          await page.emulateMedia({ forcedColors })
          for (const [selector, location] of [
            ['.workshop-logo', 'shell'],
            ['.branding-preview', 'preview'],
          ] as const) {
            const image = page.locator(selector)
            await expectLogoCanvas(image, tone, `data:image/png;base64,${artwork.logo!.png_base64}`)
            await captureLogo(
              image,
              info,
              `logo-${theme.id}-${scheme}-${tone}-${forcedColors}-${location}`,
            )
          }
        }
        await page.emulateMedia({ forcedColors: 'none' })
      }
      // Keep the original forced-color full-page light-art scene unchanged.
      const restored = await put(
        request,
        owner,
        f.locationA,
        input(saved.display_name, theme.palette, version, saved.logo!.png_base64),
      )
      version = restored.version
      await refresh(page)
      await expectBrand(page, restored)
      await loadEditor(page, f.locationA)
    }
    await page.setViewportSize({ width: 320, height: 1000 })
    await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' })
    const name = page.getByLabel('Nombre visible del taller', { exact: true })
    await name.focus()
    await page.keyboard.press('Tab')
    await expect(
      page.getByRole('combobox', { name: 'Paleta compartida', exact: true }),
    ).toBeFocused()
    expect(
      await page
        .getByRole('combobox', { name: 'Paleta compartida', exact: true })
        .evaluate((element) => element.matches(':focus-visible')),
    ).toBe(true)
    await expect(
      page.getByRole('combobox', { name: 'Paleta compartida', exact: true }),
    ).not.toHaveCSS('outline-style', 'none')
    await expectLogoCanvas(page.locator('.workshop-logo'), 'light')
    await expectLogoCanvas(page.locator('.branding-preview'), 'light')
    await expectSaveWords(page, info, `${theme.id}-forced-colors`)
    await capture(page, info, `branding-${theme.id}-forced-colors-keyboard-320`)
    expect(await node!.evaluate((element) => element.isConnected)).toBe(true)
    await expect(operational).toHaveValue(draft)
    expect((await kernelSnapshot(page)).journal).toEqual(before.journal)
    await info.attach(`branding-${theme.id}-coverage`, {
      body: JSON.stringify({
        theme: theme.id,
        palette: theme.palette,
        schemes: ['light', 'dark'],
        widths: [1440, 834, 320],
        logo: 'synthetic transparent dark, light and red bicycles, both schemes and forced colors',
        cssEnlargement: 2,
        forcedColors: true,
        physicalDeviceQualification: false,
      }),
      contentType: 'application/json',
    })
  })
}
