import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  chooseLogoBacking,
  inspectLogoBacking,
  LOGO_BACKINGS,
} from '../../.tmp-personalization/src/personalization/logo-backing.js'

const rgba = (...pixels) => new Uint8ClampedArray(pixels.flat())
function luminance(channels) {
  return channels
    .map((byte) => byte / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0)
}
function contrast(ink, plate) {
  const a = luminance(ink),
    b = luminance(plate)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}
for (const [name, ink, expected] of [
  ['light', [244, 250, 245], 'dark'],
  ['dark', [24, 60, 50], 'light'],
  ['red', [210, 69, 53], 'light'],
]) {
  test(`transparent ${name} artwork has a contrasting plate without changing source pixels`, () => {
    const pixels = rgba([...ink, 255], [0, 0, 0, 0])
    const original = pixels.slice()
    const result = chooseLogoBacking(pixels)
    assert.equal(result, expected)
    const plate = LOGO_BACKINGS[result]
      .slice(1)
      .match(/../g)
      .map((c) => parseInt(c, 16))
    assert.ok(contrast(ink, plate) >= 4.5)
    assert.deepEqual(pixels, original)
  })
}

test('partially opaque ink is scored after compositing, not by raw mean luminance', () => {
  const gray = [121, 121, 121]
  assert.ok(contrast(gray, [255, 255, 255]) > contrast(gray, [32, 32, 32]))
  const composite = (plate) =>
    gray.map((c) => Math.round((128 / 255) * c + (1 - 128 / 255) * plate))
  assert.ok(contrast(composite(32), [32, 32, 32]) > contrast(composite(255), [255, 255, 255]))
  assert.equal(chooseLogoBacking(rgba([...gray, 128])), 'dark')
})

test('mixed partially opaque artwork uses aggregate composited contrast without per-stroke guarantees', () => {
  const pixels = [
    [244, 250, 245, 90],
    [24, 60, 50, 255],
    [210, 69, 53, 180],
    [255, 255, 255, 0],
  ]
  function score(plate) {
    return pixels
      .filter((p) => p[3] >= 16)
      .reduce((sum, p) => {
        const alpha = p[3] / 255
        const composite = p.slice(0, 3).map((c) => Math.round(alpha * c + (1 - alpha) * plate))
        return sum + alpha * contrast(composite, [plate, plate, plate])
      }, 0)
  }
  assert.equal(chooseLogoBacking(rgba(...pixels)), score(32) > score(255) ? 'dark' : 'light')
})

test('transparent and near-zero alpha RGB cannot choose the backing', () => {
  for (const alpha of [0, 1, 15]) {
    assert.equal(chooseLogoBacking(rgba([255, 255, 255, alpha])), 'light')
    assert.equal(chooseLogoBacking(rgba([0, 0, 0, alpha])), 'light')
    assert.equal(chooseLogoBacking(rgba([24, 60, 50, 255], [255, 255, 255, alpha])), 'light')
  }
  assert.equal(chooseLogoBacking(rgba([255, 255, 255, 16])), 'dark')
})

test('opaque, empty and invalid or oversized pixel arrays keep the white fallback', () => {
  for (const pixels of [
    rgba([255, 255, 255, 255]),
    rgba([0, 0, 0, 255]),
    rgba(),
    new Uint8ClampedArray(3),
    new Uint8ClampedArray(512 * 512 * 4 + 4),
  ]) {
    assert.equal(chooseLogoBacking(pixels), 'light')
  }
  assert.equal(chooseLogoBacking(new Uint8ClampedArray(512 * 512 * 4)), 'light')
})

const source = 'data:image/png;base64,synthetic-unit-fixture'
function currentImage(changes = {}) {
  return {
    isConnected: true,
    complete: true,
    currentSrc: source,
    naturalWidth: 2,
    naturalHeight: 1,
    getAttribute: () => source,
    ...changes,
  }
}
const lightPixels = () => rgba([244, 250, 245, 255], [0, 0, 0, 0])

test('only a connected, complete, exact-current PNG can allocate an inspection canvas', () => {
  let reads = 0
  for (const changes of [
    { isConnected: false },
    { complete: false },
    { currentSrc: 'old-source' },
    { getAttribute: () => 'new-source' },
  ]) {
    assert.equal(
      inspectLogoBacking(currentImage(changes), source, () => {
        reads++
        return lightPixels()
      }),
      null,
    )
  }
  assert.equal(
    inspectLogoBacking(currentImage(), 'https://example.invalid/logo.png', () => {
      reads++
      return lightPixels()
    }),
    null,
  )
  assert.equal(reads, 0)
})

test('dimensions are bounded before allocating or reading pixels', () => {
  let reads = 0
  for (const [width, height] of [
    [0, 1],
    [1, 0],
    [513, 1],
    [1, 513],
    [512, 513],
    [-1, 1],
    [1.5, 1],
    [Infinity, 1],
  ]) {
    assert.equal(
      inspectLogoBacking(
        currentImage({ naturalWidth: width, naturalHeight: height }),
        source,
        () => {
          reads++
          return lightPixels()
        },
      ),
      'light',
    )
  }
  assert.equal(reads, 0)
  assert.equal(
    inspectLogoBacking(
      currentImage({ naturalWidth: 512, naturalHeight: 512 }),
      source,
      () => new Uint8ClampedArray(512 * 512 * 4),
    ),
    'light',
  )
})

test('canvas failure or malformed pixel count preserves the existing white fallback', () => {
  assert.equal(
    inspectLogoBacking(currentImage(), source, () => {
      throw new Error('unavailable or tainted')
    }),
    'light',
  )
  assert.equal(
    inspectLogoBacking(currentImage(), source, () => rgba([244, 250, 245, 255])),
    'light',
  )
  assert.equal(inspectLogoBacking(currentImage(), source, lightPixels), 'dark')
})

test('a source change or unmount during inspection cannot publish an obsolete backing', () => {
  for (const change of [
    (image) => {
      image.currentSrc = 'old-source'
    },
    (image) => {
      image.getAttribute = () => 'replacement-source'
    },
    (image) => {
      image.isConnected = false
    },
  ]) {
    const image = currentImage()
    assert.equal(
      inspectLogoBacking(image, source, () => {
        change(image)
        return lightPixels()
      }),
      null,
    )
  }
  const image = currentImage()
  assert.equal(
    inspectLogoBacking(image, source, () => {
      image.isConnected = false
      throw new Error('failed read after detach')
    }),
    null,
  )
})

test('all three image sites share render-only source-keyed backing and preserve error semantics', () => {
  const source = (path) => readFileSync(new URL(`../../src/${path}`, import.meta.url), 'utf8')
  const shell = source('personalization/WorkshopShell.tsx')
  const panel = source('features/branding/BrandingPanel.tsx')
  const renderer = source('personalization/LogoImage.tsx')
  assert.equal([...shell.matchAll(/<LogoImage/g)].length, 2)
  assert.equal([...panel.matchAll(/<LogoImage/g)].length, 1)
  assert.match(shell, /onError=\{\(\) => setBrokenLogo\(rendered.logoDataUrl\)\}/)
  assert.match(panel, /onError=\{\(\) => setBrokenPreview\(logo\)\}/)
  assert.match(renderer, /plate\?\.source === src \? plate.backing : 'light'/)
  assert.match(renderer, /\{\.\.\.props\}/)
  assert.match(renderer, /src=\{src\}/)
  assert.doesNotMatch(
    renderer + source('personalization/logo-backing.ts'),
    /toDataURL|toBlob|fetch\(|localStorage|indexedDB|filter:/,
  )
})

test('image-only forced colors and scoped whole-word reflow remain intrinsic', () => {
  const styles = readFileSync(new URL('../../src/styles.css', import.meta.url), 'utf8')
  const branding = readFileSync(
    new URL('../../src/features/branding/branding.css', import.meta.url),
    'utf8',
  )
  assert.match(styles, /\.logo-image\s*\{[^}]*forced-color-adjust: none;/s)
  assert.match(styles, /\.logo-image\[data-logo-backing\]\s*\{[^}]*border-color: CanvasText;/s)
  assert.match(
    branding,
    /\.branding-panel button\[type\]\s*\{[^}]*width: 100%;[^}]*margin-inline: 0;[^}]*white-space: normal;[^}]*overflow-wrap: normal;/s,
  )
  assert.match(
    branding,
    /\.branding-panel \.branding-form\s*\{[^}]*padding-inline: clamp\(8px, 2%, 16px\);/s,
  )
  assert.match(branding, /\.branding-panel \.branding-form fieldset\s*\{[^}]*padding-inline: 8px;/s)
  assert.doesNotMatch(branding, /text-overflow|overflow: hidden|white-space: nowrap|zoom:/)
})
