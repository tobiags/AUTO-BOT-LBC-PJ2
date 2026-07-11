import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function headers() {
  return {
    'Content-Type': 'application/json',
    'X-Control-Tower-Token': process.env.CONTROL_TOWER_TOKEN ?? '',
    'X-Operator-Role': 'operator',
    'X-Operator-Id': 'dashboard',
  }
}

export async function GET() {
  const response = await fetch(`${API_URL}/api/v1/operations/browser-use/tasks`, {
    headers: headers(), cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const response = await fetch(`${API_URL}/api/v1/operations/browser-use/tasks`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ ...body, idempotency_key: crypto.randomUUID() }),
    cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
