import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ connector: string }> },
) {
  const token = process.env.CONTROL_TOWER_TOKEN
  if (!token) {
    return NextResponse.json({ error: 'Control Tower non configure' }, { status: 503 })
  }
  const { connector } = await context.params
  const body = await request.json()
  if (body.action !== 'probe') {
    return NextResponse.json({ error: 'Session admin requise' }, { status: 403 })
  }
  const response = await fetch(
    `${API_URL}/api/v1/operations/connectors/${encodeURIComponent(connector)}/commands`,
    {
      method: 'POST',
      headers: { ...controlApiHeaders(request), 'X-Control-Tower-Token': token },
      body: JSON.stringify({
        action: body.action,
        idempotency_key: crypto.randomUUID(),
      }),
      cache: 'no-store',
    },
  )
  const payload = await response.json()
  return NextResponse.json(payload, { status: response.status })
}
