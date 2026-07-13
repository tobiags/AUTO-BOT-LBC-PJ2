import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function GET(request: NextRequest) {
  const phone = request.nextUrl.searchParams.get('phone') ?? ''
  const response = await fetch(`${API_URL}/api/v1/contacts/lookup?phone=${encodeURIComponent(phone)}`, {
    headers: controlApiHeaders(request),
    cache: 'no-store',
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
