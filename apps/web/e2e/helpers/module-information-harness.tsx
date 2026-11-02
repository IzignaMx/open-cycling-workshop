// Test-only real React composition. This file is never an entry in the PWA build.
import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ModuleInformation } from '../../src/features/module-information/ModuleInformation.js'
import {
  officialModuleReference,
  type OfficialModuleReference,
} from '../../src/features/module-information/reference.js'
import { CustomerQuickCreate } from '../../src/features/customers/CustomerQuickCreate.js'
import { OrderQuickIntake } from '../../src/features/orders/OrderQuickIntake.js'
import type { CustomerDraftState, OrderDraftState } from '../../src/features/draft-state.js'
import '../../src/styles.css'
import '../../src/features/module-information/module-information.css'

const mode = document.body.dataset.fixtureMode
const probe = { renderAttempts: 0 }
Object.assign(window, { moduleInformationFixtureProbe: probe })
const throwingReference: OfficialModuleReference = {
  ...officialModuleReference,
  get name(): string {
    probe.renderAttempts++
    throw new Error('module-render-private-error-canary')
  },
}
const reference =
  mode === 'omit' ? null : mode === 'throw' ? throwingReference : officialModuleReference
function noBusinessDispatch(): Promise<void> {
  throw new Error('This isolated UI harness does not execute business commands')
}
function Fixture() {
  const [customer, setCustomer] = useState<CustomerDraftState>({
    displayName: 'Cliente del arnés',
    email: '',
    phone: '',
  })
  const [order, setOrder] = useState<OrderDraftState>({
    customerId: 'fixture-customer',
    priority: 'normal',
    reportedProblem: 'Orden del arnés',
    intakeCondition: '',
    accessories: '',
    withBicycle: false,
    brand: '',
    model: '',
  })
  return (
    <main className="workshop-panel" style={{ maxWidth: 800, margin: '24px auto', padding: 24 }}>
      <h1>Composición aislada de la referencia</h1>
      <section aria-label="Recepción de prueba">
        <h2>Recepción</h2>
        <CustomerQuickCreate
          capture={{ draft: customer, busy: false, blocked: false, dirty: true, message: null }}
          onEdit={(field, value) => setCustomer((prior) => ({ ...prior, [field]: value }))}
          onSubmit={noBusinessDispatch}
        />
        <OrderQuickIntake
          customers={[{ customer_id: 'fixture-customer', display_name: 'Cliente del arnés' }]}
          capture={{ draft: order, busy: false, blocked: false, dirty: true, message: null }}
          onEdit={(field, value) => setOrder((prior) => ({ ...prior, [field]: value }))}
          onSubmit={noBusinessDispatch}
        />
      </section>
      <ModuleInformation reference={reference} />
    </main>
  )
}
createRoot(document.getElementById('fixture-root')!).render(<Fixture />)
