export interface OrderIntakeInput {
  customerId: string
  reportedProblem: string
  intakeCondition?: string | null
  accessories?: string | null
  priority?: string
  brand?: string | null
  model?: string | null
}

export interface NormalizedOrderIntake {
  customerId: string
  reportedProblem: string
  intakeCondition: string | null
  accessories: string | null
  priority: string
  brand: string | null
  model: string | null
}

const PRIORITIES = new Set(['low', 'normal', 'high', 'urgent'])

function collapse(value: string | null | undefined): string | null {
  if (value === null || value === undefined) return null
  const normalized = value.trim().replace(/\s+/g, ' ')
  return normalized || null
}

export function normalizeOrderIntake(input: OrderIntakeInput): NormalizedOrderIntake {
  const reportedProblem = collapse(input.reportedProblem)
  if (reportedProblem === null) {
    throw new Error('El problema reportado es obligatorio')
  }
  const priority = collapse(input.priority) ?? 'normal'
  if (!PRIORITIES.has(priority)) {
    throw new Error(`Prioridad desconocida: ${priority}`)
  }
  const brand = collapse(input.brand)
  if (brand === null && collapse(input.model) !== null) {
    throw new Error('La bicicleta requiere marca cuando se indica modelo')
  }
  return {
    customerId: input.customerId,
    reportedProblem,
    intakeCondition: collapse(input.intakeCondition),
    accessories: collapse(input.accessories),
    priority,
    brand,
    model: collapse(input.model),
  }
}

export const ORDER_STATE_LABELS: Record<string, string> = {
  INTAKE: 'Recibida',
  DIAGNOSIS: 'En diagnóstico',
  AUTHORIZED: 'Autorizada',
  REJECTED: 'Rechazada',
  IN_PROGRESS: 'En trabajo',
  WAITING_FOR_PARTS: 'Esperando refacciones',
  READY: 'Lista',
  CLOSED: 'Cerrada',
  CANCELLED: 'Cancelada',
}

export const TRANSITION_ACTION_LABELS: Record<string, string> = {
  start_diagnosis: 'Iniciar diagnóstico',
  authorize: 'Autorizar',
  reject: 'Rechazar',
  start_work: 'Iniciar trabajo',
  request_parts: 'Solicitar refacciones',
  resume_work: 'Reanudar trabajo',
  mark_ready: 'Marcar lista',
  close: 'Cerrar orden',
  cancel: 'Cancelar orden',
}
