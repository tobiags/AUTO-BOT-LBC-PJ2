import { NextRequest, NextResponse } from 'next/server'
import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ workflowId: string }> },
) {
  const { workflowId } = await context.params
  const response = await fetch(
    `${API_URL}/api/v1/operations/browser-use/tasks/${encodeURIComponent(workflowId)}/stop`,
    {
      method: 'POST',
      headers: controlApiHeaders(request),
      cache: 'no-store',
    },
  )
  return NextResponse.json(await response.json(), { status: response.status })
}
