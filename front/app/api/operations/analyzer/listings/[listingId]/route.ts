import { NextRequest, NextResponse } from 'next/server'

import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ listingId: string }> },
) {
  const { listingId } = await context.params
  const response = await fetch(
    `${API_URL}/api/v1/operations/analyzer/listings/${encodeURIComponent(listingId)}`,
    {
      method: 'POST',
      headers: controlApiHeaders(request),
      body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
      cache: 'no-store',
    },
  )
  return NextResponse.json(await response.json(), { status: response.status })
}
