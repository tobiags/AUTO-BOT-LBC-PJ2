import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ workflowId: string }> },
) {
  const body = await request.json()
  const { workflowId } = await context.params
  const response = await fetch(
    `${API_URL}/api/v1/operations/workflows/${encodeURIComponent(workflowId)}/commands`,
    {
      method: 'POST', cache: 'no-store',
      headers: controlApiHeaders(request),
      body: JSON.stringify({ ...body, idempotency_key: crypto.randomUUID() }),
    },
  )
  return NextResponse.json(await response.json(), { status: response.status })
}
