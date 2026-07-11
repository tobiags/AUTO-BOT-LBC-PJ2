import { NextRequest, NextResponse } from 'next/server'

import { controlSessionSecret, createControlSession } from '@/lib/control-session'

function constantTimeEqual(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length)
  let mismatch = left.length ^ right.length
  for (let index = 0; index < length; index += 1) {
    mismatch |= (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0)
  }
  return mismatch === 0
}

export async function POST(request: NextRequest) {
  const { username, password } = await request.json()
  const expectedUser = process.env.CONTROL_TOWER_ADMIN_USER ?? 'admin'
  const expectedPassword = process.env.CONTROL_TOWER_ADMIN_PASSWORD ?? ''
  const secret = controlSessionSecret()
  if (!expectedPassword || !secret) {
    return NextResponse.json({ error: 'Authentification non configuree' }, { status: 503 })
  }
  if (
    !constantTimeEqual(String(username), expectedUser)
    || !constantTimeEqual(String(password), expectedPassword)
  ) {
    return NextResponse.json({ error: 'Identifiants invalides' }, { status: 401 })
  }
  const token = await createControlSession(expectedUser, 'admin', secret)
  const response = NextResponse.json({ ok: true, role: 'admin' })
  response.cookies.set('control_session', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
    maxAge: 12 * 60 * 60,
  })
  return response
}
