export const MAX_LOGO_INPUT_BYTES = 2 * 1024 * 1024
export const MAX_LOGO_STORED_BYTES = 256 * 1024
const PNG_SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10]

function pngDimensions(bytes: Uint8Array): { width: number; height: number } | null {
  if (bytes.length < 33 || !PNG_SIGNATURE.every((byte, i) => bytes[i] === byte)) return null
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  if (view.getUint32(8) !== 13 || view.getUint32(12) !== 0x49484452) return null
  return { width: view.getUint32(16), height: view.getUint32(20) }
}

function jpegDimensions(bytes: Uint8Array): { width: number; height: number } | null {
  if (bytes[0] !== 255 || bytes[1] !== 216) return null
  let offset = 2
  while (offset + 9 <= bytes.length) {
    if (bytes[offset] !== 255) return null
    while (bytes[offset] === 255) offset++
    const marker = bytes[offset++]
    if (marker === undefined || marker === 217 || marker === 218) return null
    const length = ((bytes[offset] ?? 0) << 8) | (bytes[offset + 1] ?? 0)
    if (length < 2 || offset + length > bytes.length) return null
    if ([0xc0, 0xc1, 0xc2].includes(marker)) {
      return {
        height: ((bytes[offset + 3] ?? 0) << 8) | (bytes[offset + 4] ?? 0),
        width: ((bytes[offset + 5] ?? 0) << 8) | (bytes[offset + 6] ?? 0),
      }
    }
    offset += length
  }
  return null
}

export function validateLogoFile(file: { type: string; size: number }, bytes: Uint8Array) {
  if (file.size <= 0 || file.size > MAX_LOGO_INPUT_BYTES || bytes.length > MAX_LOGO_INPUT_BYTES)
    throw new Error('El logo debe pesar como máximo 2 MB.')
  if (file.type !== 'image/png' && file.type !== 'image/jpeg')
    throw new Error('Elige un archivo PNG o JPEG. SVG y enlaces externos no están permitidos.')
  const dimensions = file.type === 'image/png' ? pngDimensions(bytes) : jpegDimensions(bytes)
  if (!dimensions) throw new Error('El contenido del archivo no coincide con una imagen permitida.')
  if (
    !dimensions.width ||
    !dimensions.height ||
    dimensions.width > 4096 ||
    dimensions.height > 4096 ||
    dimensions.width * dimensions.height > 8_000_000
  )
    throw new Error('El logo debe medir como máximo 4096 px por lado y 8 megapíxeles.')
  if (file.size !== bytes.length || (file.type === 'image/png' && !completePng(bytes)))
    throw new Error('El contenido del archivo no coincide con una imagen permitida o está animado.')
  return dimensions
}

function completePng(bytes: Uint8Array): boolean {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  let offset = 8
  let hasPixels = false
  while (offset + 12 <= bytes.length) {
    const length = view.getUint32(offset)
    const end = offset + 12 + length
    if (end > bytes.length) return false
    const type = view.getUint32(offset + 4)
    // APNG is not accepted, even if a browser would expose only its first frame.
    if ([0x6163544c, 0x6663544c, 0x66644154].includes(type)) return false
    if ((offset === 8 && type !== 0x49484452) || (offset !== 8 && type === 0x49484452)) return false
    let crc = 0xffffffff
    for (let i = offset + 4; i < end - 4; i++) {
      crc ^= bytes[i] ?? 0
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0)
    }
    if ((crc ^ 0xffffffff) >>> 0 !== view.getUint32(end - 4)) return false
    if (type === 0x49444154 && length > 0) hasPixels = true
    if (type === 0x49454e44) return hasPixels && length === 0 && end === bytes.length
    offset = end
  }
  return false
}

/** Only our bounded, rasterized PNG representation can be restored. Never accept a URL or SVG. */
export function isSafeStoredLogo(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > Math.ceil(MAX_LOGO_STORED_BYTES / 3) * 4 + 22)
    return false
  if (!/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(value)) return false
  try {
    const encoded = value.slice(22)
    if (encoded.length % 4 !== 0) return false
    const binary = atob(encoded)
    if (binary.length > MAX_LOGO_STORED_BYTES || binary.length < 45) return false
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0))
    const dimensions = pngDimensions(bytes)
    if (
      !dimensions ||
      dimensions.width < 1 ||
      dimensions.height < 1 ||
      dimensions.width > 512 ||
      dimensions.height > 512
    )
      return false
    // A complete PNG terminates in the zero-length IEND chunk, with its fixed CRC.
    return completePng(bytes)
  } catch {
    return false
  }
}

export async function prepareLocalLogo(file: File): Promise<string> {
  if (file.size > MAX_LOGO_INPUT_BYTES) throw new Error('El logo debe pesar como máximo 2 MB.')
  const bytes = new Uint8Array(await file.arrayBuffer())
  validateLogoFile(file, bytes)
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    throw new Error('No se pudo abrir la imagen. Prueba otro PNG o JPEG.')
  }
  try {
    if (
      !bitmap.width ||
      !bitmap.height ||
      bitmap.width > 4096 ||
      bitmap.height > 4096 ||
      bitmap.width * bitmap.height > 8_000_000
    )
      throw new Error('La imagen supera las dimensiones permitidas.')
    const scale = Math.min(1, 512 / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(bitmap.width * scale))
    canvas.height = Math.max(1, Math.round(bitmap.height * scale))
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Este navegador no pudo preparar el logo.')
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    // Re-encoding strips EXIF, metadata and the original file name.
    const dataUrl = canvas.toDataURL('image/png')
    if (!isSafeStoredLogo(dataUrl))
      throw new Error('El logo preparado supera 256 KB. Usa una imagen más sencilla.')
    return dataUrl
  } finally {
    bitmap.close()
  }
}
