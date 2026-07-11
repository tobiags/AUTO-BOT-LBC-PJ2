import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
export async function GET(request: NextRequest) {
  const response = await fetch(`${API_URL}/api/v1/operations/lab/runs`, {
    headers: controlApiHeaders(request), cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const response = await fetch(`${API_URL}/api/v1/operations/lab/runs`, {
    method: 'POST', headers: controlApiHeaders(request), cache: 'no-store',
    body: JSON.stringify({ ...body, idempotency_key: crypto.randomUUID() }),
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
