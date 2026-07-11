import { NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST(
  _request: Request,
  context: { params: Promise<{ workflowId: string }> },
) {
  const { workflowId } = await context.params
  const response = await fetch(
    `${API_URL}/api/v1/operations/lab/runs/${encodeURIComponent(workflowId)}/stop`,
    {
      method: 'POST', cache: 'no-store',
      headers: {
        'X-Control-Tower-Token': process.env.CONTROL_TOWER_TOKEN ?? '',
        'X-Operator-Role': 'admin',
        'X-Operator-Id': 'dashboard',
      },
    },
  )
  return NextResponse.json(await response.json(), { status: response.status })
}
