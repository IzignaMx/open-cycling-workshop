import type { CaptureValidationCode } from '../runtime/capture-outcome.js'

export interface CaptureFeedback {
  status: 'saved' | 'not_saved' | 'unknown'
  message: string | null
  blockSubmission: boolean
}

const unknown = (): CaptureFeedback => ({
  status: 'unknown',
  message:
    'No se pudo confirmar si el cambio se guardó. No lo envíes otra vez; verifica el estado del taller antes de continuar.',
  blockSubmission: true,
})
const validationMessages: Record<CaptureValidationCode, string> = {
  customer_name_required: 'El nombre es obligatorio',
  order_problem_required: 'El problema reportado es obligatorio',
  priority_invalid: 'Selecciona una prioridad válida',
  bicycle_brand_required: 'La bicicleta requiere marca cuando se indica modelo',
}

export function captureFeedback(
  input: { kind: 'resolved'; value: unknown } | { kind: 'rejected'; error: unknown },
): CaptureFeedback {
  if (input.kind === 'rejected') return unknown()
  try {
    const value = input.value
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return unknown()
    const record = value as Record<string, unknown>
    const ownKeys = Reflect.ownKeys(record)
    if (ownKeys.some((key) => typeof key !== 'string')) return unknown()
    const keys = (ownKeys as string[]).sort().join(',')
    if (record.status === 'saved' && keys === 'status')
      return { status: 'saved', message: null, blockSubmission: false }
    if (record.status !== 'not_saved') return unknown()
    let message: string
    if (keys === 'reason,status' && record.reason === 'quota') {
      message =
        'No se guardó: falta espacio de almacenamiento en este dispositivo. Conserva este formulario y libera espacio sin borrar los datos de esta aplicación. Después puedes volver a intentar guardar.'
    } else if (keys === 'reason,status' && record.reason === 'write_failure') {
      message =
        'No se guardó el cambio. Conserva este formulario y vuelve a intentarlo cuando el almacenamiento esté disponible.'
    } else if (
      keys === 'code,reason,status' &&
      record.reason === 'validation' &&
      typeof record.code === 'string' &&
      Object.hasOwn(validationMessages, record.code)
    ) {
      message = validationMessages[record.code as CaptureValidationCode]
    } else return unknown()
    return { status: 'not_saved', message, blockSubmission: false }
  } catch {
    return unknown()
  }
}

/** Mounted-form guard only, not a durable cross-navigation idempotency mechanism. */
export class CaptureSubmissionGate {
  private busy = false
  blocked = false
  begin(): boolean {
    if (this.busy || this.blocked) return false
    this.busy = true
    return true
  }
  finish(feedback: CaptureFeedback): void {
    this.blocked ||= feedback.blockSubmission
    this.busy = false
  }
}
