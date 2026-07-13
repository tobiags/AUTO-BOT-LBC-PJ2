import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ campaignId: string }> },
) {
  const { campaignId } = await context.params
  const response = await fetch(`${API_URL}/campaigns/${encodeURIComponent(campaignId)}/templates`, {
    headers: controlApiHeaders(request),
    cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ campaignId: string }> },
) {
  const { campaignId } = await context.params
  const response = await fetch(`${API_URL}/campaigns/${encodeURIComponent(campaignId)}/templates`, {
    method: 'PUT',
    headers: controlApiHeaders(request),
    body: JSON.stringify(await request.json()),
    cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
