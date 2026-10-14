import { useLayoutEffect, useRef, type RefObject } from 'react'
import type { AdministrationController } from './controller.js'

export type PanelProps = { controller: AdministrationController }
export type AdministrationSnapshot = ReturnType<AdministrationController['getSnapshot']>
export type ConnectedProps = PanelProps & { snapshot: AdministrationSnapshot }

/** Credentials belong only to mounted DOM controls, never shared feature state. */
export function useSecret(
  controller: AdministrationController,
): RefObject<HTMLInputElement | null> {
  const ref = useRef<HTMLInputElement>(null)
  useLayoutEffect(() => {
    const generation = controller.getSnapshot().generation
    const clear = () => {
      const input = ref.current
      if (input) input.value = ''
    }
    const unsubscribe = controller.subscribe(() => {
      const current = controller.getSnapshot()
      if (current.generation !== generation || current.account.phase !== 'connected') clear()
    })
    return () => {
      clear()
      unsubscribe()
    }
  }, [controller])
  return ref
}
export function takeSecret(ref: RefObject<HTMLInputElement | null>): string {
  const input = ref.current
  if (!input) return ''
  const value = input.value
  input.value = ''
  return value
}
export const discardDraft = () => window.confirm('¿Descartar los cambios sin guardar?')
export function SecurityNotice({ self = false }: { self?: boolean }) {
  return (
    <p>
      {self
        ? 'Esta acción cerrará tu sesión y bloqueará el trabajo operativo. Los cambios locales ya guardados se conservan; guarda antes los formularios pendientes.'
        : 'Esta acción cambia el acceso de la cuenta. Las sesiones remotas sin conexión pueden conservar su autorización hasta que expire su plazo local.'}
    </p>
  )
}
