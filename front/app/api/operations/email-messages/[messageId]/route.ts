import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(request: NextRequest, { params }: { params: Promise<{ messageId: string }> }) {
  const { messageId } = await params
  const response = await fetch(`${API_URL}/api/v1/email-messages/${messageId}/read`, {
    method: 'POST', headers: controlApiHeaders(request), cache: 'no-store',
  })
  return new NextResponse(await response.text(), { status: response.status, headers: { 'Content-Type': response.headers.get('Content-Type') ?? 'application/json' } })
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ messageId: string }> }) {
  const { messageId } = await params
  const response = await fetch(`${API_URL}/api/v1/email-messages/${messageId}`, {
    method: 'DELETE', headers: controlApiHeaders(request), cache: 'no-store',
  })
  return new NextResponse(null, { status: response.status })
}
