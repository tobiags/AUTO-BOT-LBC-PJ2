import { NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST() {
  const response = await fetch(`${API_URL}/api/v1/operations/messaging/sync`, {
    method: 'POST', cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      'X-Control-Tower-Token': process.env.CONTROL_TOWER_TOKEN ?? '',
      'X-Operator-Role': 'operator',
      'X-Operator-Id': 'dashboard',
    },
    body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
