export const LOGO_BACKINGS = { light: '#ffffff', dark: '#202020' } as const
export type LogoBacking = keyof typeof LOGO_BACKINGS
const MAX_SIDE = 512
const MAX_PIXELS = MAX_SIDE * MAX_SIDE
const LINEAR = Array.from({ length: 256 }, (_, byte) => {
  const c = byte / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
})
function luminance(r: number, g: number, b: number) {
  return 0.2126 * LINEAR[r]! + 0.7152 * LINEAR[g]! + 0.0722 * LINEAR[b]!
}
function contrast(a: number, b: number) {
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

// Presentation-only heuristic, not a contrast guarantee for every mixed-artwork
// stroke. Score the actual alpha-composited sRGB8 pixels, never hidden RGB or a
// raw average luminance. Original image bytes and pixels are never rewritten.
export function chooseLogoBacking(pixels: Uint8ClampedArray): LogoBacking {
  if (!pixels.length || pixels.length % 4 || pixels.length > MAX_PIXELS * 4) return 'light'
  let whiteScore = 0,
    darkScore = 0,
    transparent = false
  const darkLuminance = luminance(32, 32, 32)
  for (let i = 0; i < pixels.length; i += 4) {
    const opacity = pixels[i + 3]!
    if (opacity < 255) transparent = true
    // Nearly invisible pixels must not let arbitrary transparent RGB pick a plate.
    if (opacity < 16) continue
    const alpha = opacity / 255
    const composite = (plate: number) =>
      luminance(
        Math.round(alpha * pixels[i]! + (1 - alpha) * plate),
        Math.round(alpha * pixels[i + 1]! + (1 - alpha) * plate),
        Math.round(alpha * pixels[i + 2]! + (1 - alpha) * plate),
      )
    whiteScore += alpha * contrast(composite(255), 1)
    darkScore += alpha * contrast(composite(32), darkLuminance)
  }
  // Opaque artwork supplies its own background. Ties/no visible samples retain
  // the existing white plate. Dividing both scores by alpha mass is unnecessary.
  return transparent && darkScore > whiteScore ? 'dark' : 'light'
}

function currentImage(image: HTMLImageElement, source: string) {
  return (
    image.isConnected &&
    image.complete &&
    source.startsWith('data:image/png;base64,') &&
    image.getAttribute('src') === source &&
    image.currentSrc === source
  )
}
function decodedPixels(image: HTMLImageElement) {
  const canvas = document.createElement('canvas')
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Logo canvas unavailable')
  context.drawImage(image, 0, 0)
  return context.getImageData(0, 0, canvas.width, canvas.height).data
}

// The injected reader permits bounded failure/lifecycle tests; production reads
// only this already-decoded image synchronously, with no new request or encoder.
export function inspectLogoBacking(
  image: HTMLImageElement,
  source: string,
  readPixels: (image: HTMLImageElement) => Uint8ClampedArray = decodedPixels,
): LogoBacking | null {
  if (!currentImage(image, source)) return null
  const width = image.naturalWidth,
    height = image.naturalHeight
  if (
    !Number.isSafeInteger(width) ||
    !Number.isSafeInteger(height) ||
    width < 1 ||
    height < 1 ||
    width > MAX_SIDE ||
    height > MAX_SIDE ||
    width * height > MAX_PIXELS
  )
    return 'light'
  let backing: LogoBacking = 'light'
  try {
    const pixels = readPixels(image)
    if (pixels.length === width * height * 4) backing = chooseLogoBacking(pixels)
  } catch {
    // An unavailable/tainted canvas is not a broken image or permission to alter
    // the asset. Keep the original white presentation fallback.
  }
  return currentImage(image, source) ? backing : null
}
