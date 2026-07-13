import { NextRequest, NextResponse } from 'next/server'
import { API_URL, workspaceHeaders } from '@/lib/workspace-api'

export async function GET(request: NextRequest, context: { params: Promise<{ sectorId: string }> }) {
  const headers = await workspaceHeaders(request)
  if (!headers) return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  const { sectorId } = await context.params
  const response = await fetch(`${API_URL}/api/v1/workspace/sectors/${sectorId}/resources`, { headers, cache: 'no-store' })
  return NextResponse.json(await response.json(), { status: response.status })
}

export async function PUT(request: NextRequest, context: { params: Promise<{ sectorId: string }> }) {
  const headers = await workspaceHeaders(request)
  if (!headers) return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  const { sectorId } = await context.params
  const response = await fetch(`${API_URL}/api/v1/workspace/sectors/${sectorId}/resources`, { method: 'POST', headers, body: JSON.stringify(await request.json()), cache: 'no-store' })
  return NextResponse.json(await response.json(), { status: response.status })
}
