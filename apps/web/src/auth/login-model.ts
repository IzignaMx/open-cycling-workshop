export interface LoginFormInput {
  organizationId: string
  username: string
  password: string
}

export interface LoginRequestPayload {
  organization_id: string
  username: string
  password: string
}

export function buildLoginRequest(input: LoginFormInput): LoginRequestPayload {
  const organizationId = input.organizationId.trim()
  const username = input.username.trim()
  if (!organizationId) throw new Error('Organization is required')
  if (!username) throw new Error('Username is required')
  if (!input.password) throw new Error('Password is required')
  return {
    organization_id: organizationId,
    username,
    password: input.password,
  }
}
