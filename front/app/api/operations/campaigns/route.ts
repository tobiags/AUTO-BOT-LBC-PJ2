import { NextRequest, NextResponse } from 'next/server'

import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(request: NextRequest) {
  const body = await request.json()
  const response = await fetch(`${API_URL}/api/v1/operations/campaigns`, {
    method: 'POST',
    headers: controlApiHeaders(request),
    body: JSON.stringify({ ...body, idempotency_key: crypto.randomUUID() }),
    cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
