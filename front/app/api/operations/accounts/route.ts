import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(request: NextRequest) {
  const body = await request.json()
  const response = await fetch(`${API_URL}/api/v1/operations/accounts/commands`, {
    method: 'POST', cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      'X-Control-Tower-Token': process.env.CONTROL_TOWER_TOKEN ?? '',
      'X-Operator-Role': 'admin',
      'X-Operator-Id': 'dashboard',
    },
    body: JSON.stringify({ ...body, idempotency_key: crypto.randomUUID() }),
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
