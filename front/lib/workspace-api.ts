import { cookies } from 'next/headers'
import { controlApiHeaders } from './control-api'
import { controlSessionSecret, verifyControlSession } from './control-session'

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function workspaceHeaders(request: Request) {
  const session = await verifyControlSession(
    (await cookies()).get('control_session')?.value,
    controlSessionSecret(),
  )
  if (!session) return null
  const role = session.role === 'admin' ? 'administrateur' : session.role === 'manager' ? 'manager' : 'operateur'
  return { ...controlApiHeaders(request as never), 'X-Operator-Role': role, 'X-Operator-Id': session.sub }
}
