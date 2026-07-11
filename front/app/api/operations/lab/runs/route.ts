import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const headers = () => ({
  'Content-Type': 'application/json',
  'X-Control-Tower-Token': process.env.CONTROL_TOWER_TOKEN ?? '',
  'X-Operator-Role': 'admin',
  'X-Operator-Id': 'dashboard',
})

export async function GET() {
  const response = await fetch(`${API_URL}/api/v1/operations/lab/runs`, {
    headers: headers(), cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const response = await fetch(`${API_URL}/api/v1/operations/lab/runs`, {
    method: 'POST', headers: headers(), cache: 'no-store',
    body: JSON.stringify({ ...body, idempotency_key: crypto.randomUUID() }),
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
