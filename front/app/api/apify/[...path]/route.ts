import { NextRequest, NextResponse } from 'next/server'

import { controlApiHeaders } from '@/lib/control-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function proxy(request: NextRequest, segments: string[]) {
  const token = process.env.CONTROL_TOWER_TOKEN
  if (!token) {
    return NextResponse.json({ error: 'Control Tower non configure' }, { status: 503 })
  }
  const target = new URL(`/api/v1/apify/${segments.map(encodeURIComponent).join('/')}`, API_URL)
  target.search = request.nextUrl.search
  const body =
    request.method === 'GET' || request.method === 'DELETE'
      ? undefined
      : await request.text()
  const response = await fetch(target, {
    method: request.method,
    headers: {
      ...controlApiHeaders(request),
      'X-Control-Tower-Token': token,
    },
    body,
    cache: 'no-store',
  })
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') ?? 'application/json',
    },
  })
}

type Context = { params: Promise<{ path: string[] }> }

export async function GET(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path)
}

export async function POST(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path)
}

export async function PATCH(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path)
}

export async function DELETE(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path)
}
