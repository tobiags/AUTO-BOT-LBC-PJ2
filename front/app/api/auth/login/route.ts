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
  const secret = controlSessionSecret()
  const users = [
    {
      username: process.env.CONTROL_TOWER_ADMIN_USER ?? 'admin',
      password: process.env.CONTROL_TOWER_ADMIN_PASSWORD ?? '',
      role: 'admin' as const,
    },
    {
      username: process.env.CONTROL_TOWER_OPERATOR_USER ?? 'operator',
      password: process.env.CONTROL_TOWER_OPERATOR_PASSWORD ?? '',
      role: 'operator' as const,
    },
    {
      username: process.env.CONTROL_TOWER_VIEWER_USER ?? 'viewer',
      password: process.env.CONTROL_TOWER_VIEWER_PASSWORD ?? '',
      role: 'viewer' as const,
    },
  ]
  if (!users.some((user) => user.password) || !secret) {
    return NextResponse.json({ error: 'Authentification non configuree' }, { status: 503 })
  }
  const user = users.find((candidate) => (
    candidate.password
    && constantTimeEqual(String(username), candidate.username)
    && constantTimeEqual(String(password), candidate.password)
  ))
  if (!user) {
    return NextResponse.json({ error: 'Identifiants invalides' }, { status: 401 })
  }
  const token = await createControlSession(user.username, user.role, secret)
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
