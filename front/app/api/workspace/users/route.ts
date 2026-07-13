import { cookies } from 'next/headers'
import { NextRequest, NextResponse } from 'next/server'

import { controlApiHeaders } from '@/lib/control-api'
import { controlSessionSecret, verifyControlSession } from '@/lib/control-session'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function sessionHeaders(request: NextRequest) {
  const cookieStore = await cookies()
  const session = await verifyControlSession(
    cookieStore.get('control_session')?.value,
    controlSessionSecret(),
  )
  if (!session) return null

  const role = session.role === 'admin' ? 'administrateur' : session.role === 'manager' ? 'manager' : 'operateur'
  return {
    ...controlApiHeaders(request),
    'X-Operator-Role': role,
    'X-Operator-Id': session.sub,
  }
}

export async function GET(request: NextRequest) {
  const headers = await sessionHeaders(request)
  if (!headers) return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })

  const response = await fetch(`${API_URL}/api/v1/workspace/users`, {
    headers,
    cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}

export async function POST(request: NextRequest) {
  const headers = await sessionHeaders(request)
  if (!headers) return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  if (headers['X-Operator-Role'] !== 'administrateur') {
    return NextResponse.json({ error: 'Réservé à l’administrateur' }, { status: 403 })
  }

  const response = await fetch(`${API_URL}/api/v1/workspace/users`, {
    method: 'POST',
    headers,
    body: JSON.stringify(await request.json()),
    cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
