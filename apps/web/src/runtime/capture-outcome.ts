export type CaptureValidationCode =
  | 'customer_name_required'
  | 'order_problem_required'
  | 'priority_invalid'
  | 'bicycle_brand_required'

export type CaptureNotSaved =
  | { status: 'not_saved'; reason: 'quota' | 'write_failure' }
  | { status: 'not_saved'; reason: 'validation'; code: CaptureValidationCode }

export type CaptureSubmissionResult = { status: 'saved' } | CaptureNotSaved
export type CaptureRepositoryResult<T> = { status: 'committed'; entity: T } | CaptureNotSaved

/** Only call around synchronous, pre-write source-owned domain preparation. */
export function captureValidation(error: unknown): CaptureNotSaved | null {
  if (!(error instanceof Error)) return null
  switch (error.message) {
    case 'El nombre es obligatorio':
      return { status: 'not_saved', reason: 'validation', code: 'customer_name_required' }
    case 'El problema reportado es obligatorio':
      return { status: 'not_saved', reason: 'validation', code: 'order_problem_required' }
    case 'La bicicleta requiere marca cuando se indica modelo':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_brand_required' }
    default:
      return error.message.startsWith('Prioridad desconocida: ')
        ? { status: 'not_saved', reason: 'validation', code: 'priority_invalid' }
        : null
  }
}
