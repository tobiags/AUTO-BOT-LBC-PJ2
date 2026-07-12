import { createHmac } from 'node:crypto'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

import { controlSessionSecret, verifyControlSession } from '@/lib/control-session'

export async function GET() {
  const cookieStore = await cookies()
  const session = await verifyControlSession(
    cookieStore.get('control_session')?.value,
    controlSessionSecret(),
  )
  if (!session) return NextResponse.json({ error: 'unauthorized' }, { status: 401 })

  const key = process.env.CONTROL_TOWER_TOKEN
  if (!key) return NextResponse.json({ error: 'not_configured' }, { status: 503 })
  const expires = String(Math.floor(Date.now() / 1000) + 60)
  const signature = createHmac('sha256', key).update(expires).digest('hex')
  return NextResponse.json({ token: `${expires}.${signature}` })
}
