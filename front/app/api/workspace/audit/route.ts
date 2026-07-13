import { NextRequest, NextResponse } from 'next/server'
import { API_URL, workspaceHeaders } from '@/lib/workspace-api'

export async function GET(request: NextRequest) {
  const headers = await workspaceHeaders(request)
  if (!headers) return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  const response = await fetch(`${API_URL}/api/v1/workspace/audit?limit=200`, { headers, cache: 'no-store' })
  return NextResponse.json(await response.json(), { status: response.status })
}
