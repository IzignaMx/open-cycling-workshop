export type CaptureValidationCode =
  | 'customer_name_required'
  | 'customer_name_too_long'
  | 'customer_email_too_long'
  | 'customer_email_invalid'
  | 'customer_phone_too_long'
  | 'order_problem_required'
  | 'priority_invalid'
  | 'bicycle_brand_empty'
  | 'bicycle_brand_too_long'
  | 'bicycle_model_too_long'
  | 'bicycle_type_too_long'
  | 'bicycle_wheel_too_long'
  | 'bicycle_notes_too_long'
  | 'priority_required'
  | 'priority_too_long'
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
    case 'El nombre no puede superar 200 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'customer_name_too_long' }
    case 'El correo no es válido':
      return { status: 'not_saved', reason: 'validation', code: 'customer_email_invalid' }
    case 'El correo no puede superar 320 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'customer_email_too_long' }
    case 'El teléfono no puede superar 64 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'customer_phone_too_long' }
    case 'El problema reportado es obligatorio':
      return { status: 'not_saved', reason: 'validation', code: 'order_problem_required' }
    case 'La bicicleta requiere marca cuando se indica modelo':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_brand_required' }
    case 'La marca de la bicicleta es obligatoria':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_brand_empty' }
    case 'La marca no puede superar 120 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_brand_too_long' }
    case 'El modelo no puede superar 120 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_model_too_long' }
    case 'El tipo de bicicleta no puede superar 60 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_type_too_long' }
    case 'El tamaño de rueda no puede superar 30 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_wheel_too_long' }
    case 'Las notas de la bicicleta no pueden superar 2000 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'bicycle_notes_too_long' }
    case 'La prioridad es obligatoria':
      return { status: 'not_saved', reason: 'validation', code: 'priority_required' }
    case 'La prioridad no puede superar 30 caracteres':
      return { status: 'not_saved', reason: 'validation', code: 'priority_too_long' }
    default:
      return error.message.startsWith('Prioridad desconocida: ')
        ? { status: 'not_saved', reason: 'validation', code: 'priority_invalid' }
        : null
  }
}
