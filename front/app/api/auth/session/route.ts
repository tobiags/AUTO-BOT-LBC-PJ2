import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

import { controlSessionSecret, verifyControlSession } from '@/lib/control-session'

export async function GET() {
  const cookieStore = await cookies()
  const session = await verifyControlSession(
    cookieStore.get('control_session')?.value,
    controlSessionSecret(),
  )
  if (!session) return NextResponse.json({ authenticated: false }, { status: 401 })
  return NextResponse.json({
    authenticated: true,
    operator: session.sub,
    role: session.role,
    expires_at: session.exp,
  })
}
