export function shouldClearSessionAfterAuthError(status: number | null): boolean {
  return status === 401 || status === 403
}
