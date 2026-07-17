import { NextRequest, NextResponse } from 'next/server'

import { controlSessionSecret, verifyControlSession } from './lib/control-session'

export async function middleware(request: NextRequest) {
  const session = await verifyControlSession(
    request.cookies.get('control_session')?.value,
    controlSessionSecret(),
  )
  if (session) {
    if (
      request.nextUrl.pathname.startsWith('/api/operations')
      && session.role === 'viewer'
      && request.method !== 'GET'
    ) {
      return NextResponse.json({ error: 'Role operateur requis' }, { status: 403 })
    }
    const headers = new Headers(request.headers)
    headers.set('x-control-role', session.role)
    headers.set('x-control-user', session.sub)
    return NextResponse.next({ request: { headers } })
  }
  if (request.nextUrl.pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'Authentification requise' }, { status: 401 })
  }
  const login = new URL('/login', request.url)
  login.searchParams.set('next', request.nextUrl.pathname)
  return NextResponse.redirect(login)
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/workflows/:path*',
    '/listings/:path*',
    '/campaigns/:path*',
    '/messaging/:path*',
    '/accounts/:path*',
    '/analyzer/:path*',
    '/connectors/:path*',
    '/browser-use/:path*',
    '/lab/:path*',
    '/apify/:path*',
    '/phones/:path*',
    '/settings/:path*',
    '/api/operations/:path*',
    '/api/apify/:path*',
    '/api/phone-operations/:path*',
  ],
}
