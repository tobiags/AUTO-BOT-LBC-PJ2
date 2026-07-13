import { NextRequest, NextResponse } from 'next/server'

import { controlSessionSecret, createControlSession, type ControlRole } from '@/lib/control-session'

export async function POST(request: NextRequest) {
  const { username, password } = await request.json()
  const secret = controlSessionSecret()
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  const controlToken = process.env.CONTROL_TOWER_TOKEN
  if (!secret || !controlToken) {
    return NextResponse.json({ error: 'Authentification non configuree' }, { status: 503 })
  }
  const backend = await fetch(`${baseUrl}/api/v1/workspace/authenticate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Control-Tower-Token': controlToken },
    body: JSON.stringify({ email: username, password }),
  })
  if (!backend.ok) {
    return NextResponse.json({ error: 'Identifiants invalides' }, { status: backend.status === 401 ? 401 : 503 })
  }
  const user = await backend.json() as { email: string; role: 'administrateur' | 'manager' | 'operateur' }
  const controlRole: ControlRole = user.role === 'administrateur' ? 'admin' : 'operator'
  const token = await createControlSession(user.email, controlRole, secret)
  const response = NextResponse.json({ ok: true, role: user.role })
  response.cookies.set('control_session', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
    maxAge: 12 * 60 * 60,
  })
  return response
}
