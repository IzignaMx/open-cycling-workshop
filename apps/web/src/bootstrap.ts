export type BootstrapBlock = 'insecure-context' | 'storage-unavailable'

/** No storage probe, runtime construction or recovery on a blocked bootstrap. */
export function bootstrap(
  environment: { readonly isSecureContext: boolean; readonly sessionStorage: Storage },
  start: (storage: Storage) => void,
  blocked: (reason: BootstrapBlock) => void,
): void {
  if (environment.isSecureContext !== true) {
    blocked('insecure-context')
    return
  }
  let storage: Storage
  try {
    storage = environment.sessionStorage
  } catch {
    blocked('storage-unavailable')
    return
  }
  start(storage)
}
