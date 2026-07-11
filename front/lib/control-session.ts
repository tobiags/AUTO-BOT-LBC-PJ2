export type ControlRole = 'operator' | 'admin'

export type ControlSession = {
  sub: string
  role: ControlRole
  exp: number
}

const encoder = new TextEncoder()

function base64url(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
}

function decodeBase64url(value: string): Uint8Array {
  const padded = value.replaceAll('-', '+').replaceAll('_', '/')
    .padEnd(Math.ceil(value.length / 4) * 4, '=')
  const binary = atob(padded)
  return Uint8Array.from(binary, (character) => character.charCodeAt(0))
}

async function signature(payload: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  )
  const signed = await crypto.subtle.sign('HMAC', key, encoder.encode(payload))
  return base64url(new Uint8Array(signed))
}

function constantTimeEqual(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length)
  let mismatch = left.length ^ right.length
  for (let index = 0; index < length; index += 1) {
    mismatch |= (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0)
  }
  return mismatch === 0
}

export async function createControlSession(
  subject: string,
  role: ControlRole,
  secret: string,
): Promise<string> {
  const session: ControlSession = {
    sub: subject,
    role,
    exp: Math.floor(Date.now() / 1000) + 12 * 60 * 60,
  }
  const payload = base64url(encoder.encode(JSON.stringify(session)))
  return `${payload}.${await signature(payload, secret)}`
}

export async function verifyControlSession(
  token: string | undefined,
  secret: string,
): Promise<ControlSession | null> {
  if (!token || !secret) return null
  const [payload, providedSignature, extra] = token.split('.')
  if (!payload || !providedSignature || extra) return null
  const expectedSignature = await signature(payload, secret)
  if (!constantTimeEqual(providedSignature, expectedSignature)) return null
  try {
    const session = JSON.parse(
      new TextDecoder().decode(decodeBase64url(payload)),
    ) as ControlSession
    if (session.exp <= Math.floor(Date.now() / 1000)) return null
    if (!['operator', 'admin'].includes(session.role)) return null
    return session
  } catch {
    return null
  }
}

export function controlSessionSecret(): string {
  return process.env.CONTROL_TOWER_SESSION_SECRET
    ?? process.env.CONTROL_TOWER_TOKEN
    ?? ''
}
