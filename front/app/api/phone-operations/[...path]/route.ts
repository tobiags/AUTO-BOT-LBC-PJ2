import { NextRequest, NextResponse } from 'next/server'

import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function proxy(request: NextRequest, segments: string[]) {
  const token = process.env.CONTROL_TOWER_TOKEN
  if (!token) return NextResponse.json({ error: 'Control Tower non configure' }, { status: 503 })
  const target = new URL(
    `/api/v1/phone-operations/${segments.map(encodeURIComponent).join('/')}`,
    API_URL,
  )
  target.search = request.nextUrl.search
  const body = request.method === 'GET' ? undefined : await request.text()
  const response = await fetch(target, {
    method: request.method,
    headers: { ...controlApiHeaders(request), 'X-Control-Tower-Token': token },
    body,
    cache: 'no-store',
  })
  const headers = new Headers()
  headers.set('Content-Type', response.headers.get('Content-Type') ?? 'application/json')
  const disposition = response.headers.get('Content-Disposition')
  if (disposition) headers.set('Content-Disposition', disposition)
  return new NextResponse(await response.arrayBuffer(), { status: response.status, headers })
}

type Context = { params: Promise<{ path: string[] }> }

export async function GET(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path)
}

export async function POST(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path)
}
