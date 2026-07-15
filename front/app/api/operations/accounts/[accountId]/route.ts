import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ accountId: string }> },
) {
  const body = await request.json()
  const { accountId } = await context.params
  const response = await fetch(
    `${API_URL}/api/v1/operations/accounts/${encodeURIComponent(accountId)}/commands`,
    {
      method: 'POST', cache: 'no-store',
      headers: controlApiHeaders(request),
      body: JSON.stringify({ ...body, idempotency_key: crypto.randomUUID() }),
    },
  )
  return NextResponse.json(await response.json(), { status: response.status })
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ accountId: string }> },
) {
  const { accountId } = await context.params
  const response = await fetch(
    `${API_URL}/api/v1/operations/accounts/${encodeURIComponent(accountId)}`,
    {
      method: 'DELETE', cache: 'no-store',
      headers: controlApiHeaders(request),
    },
  )
  return NextResponse.json(await response.json(), { status: response.status })
}
