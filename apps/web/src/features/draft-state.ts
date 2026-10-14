/** Current unsent UI values only. No persistence, journal inspection or input-history latch. */
export interface CustomerDraftState {
  displayName: string
  email: string
  phone: string
}
export interface RetainedOrderSelection {
  customerId: string
  priority: string
}
export interface OrderDraftState extends RetainedOrderSelection {
  reportedProblem: string
  intakeCondition: string
  accessories: string
  withBicycle: boolean
  brand: string
  model: string
}
export function hasCustomerDraft(draft: CustomerDraftState): boolean {
  return draft.displayName !== '' || draft.email !== '' || draft.phone !== ''
}
export function hasOrderDraft(
  draft: OrderDraftState,
  retained: RetainedOrderSelection = { customerId: '', priority: 'normal' },
): boolean {
  return (
    draft.customerId !== retained.customerId ||
    draft.priority !== retained.priority ||
    draft.reportedProblem !== '' ||
    draft.intakeCondition !== '' ||
    draft.accessories !== '' ||
    draft.withBicycle ||
    draft.brand !== '' ||
    draft.model !== ''
  )
}
/** Query at the navigation boundary so React's latest model, including successful resets,
 * is authoritative. Search, personal theme controls and historical edits are not drafts. */
export function hasUnsentForms(root: Pick<Document, 'querySelector'>): boolean {
  return (
    root.querySelector(
      '[data-runtime-state="READY"] form[data-dirty="true"], #workshop-administration [data-dirty="true"]',
    ) !== null
  )
}
