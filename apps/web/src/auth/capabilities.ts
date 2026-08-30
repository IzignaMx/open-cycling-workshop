export function hasCapability(capabilities: readonly string[], required: string): boolean {
  return capabilities.includes('*') || capabilities.includes(required)
}
