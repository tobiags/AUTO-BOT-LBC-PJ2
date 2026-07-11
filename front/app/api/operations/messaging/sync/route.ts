import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(request: NextRequest) {
  const response = await fetch(`${API_URL}/api/v1/operations/messaging/sync`, {
    method: 'POST', cache: 'no-store',
    headers: controlApiHeaders(request),
    body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
