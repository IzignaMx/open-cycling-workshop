import { pythonWhitespace } from '../../shared/python-whitespace.js'

const whitespace = new RegExp(`[${pythonWhitespace}]+`, 'u')
/** New UI notes use the REST input bound; existing historical notes stay untouched. */
export function transitionNoteError(value: string): string | null {
  if (value.includes('\0') || /[\uD800-\uDFFF]/u.test(value))
    return 'La nota contiene caracteres no compatibles.'
  if ([...value].length > 2000) return 'La nota no puede superar 2000 caracteres.'
  return null
}
export function normalizeTransitionNote(value?: string | null): string | null {
  if (value == null) return null
  const error = transitionNoteError(value)
  if (error) throw new Error(error)
  return value.split(whitespace).filter(Boolean).join(' ') || null
}
