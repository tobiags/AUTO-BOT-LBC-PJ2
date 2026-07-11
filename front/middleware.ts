import { NextRequest, NextResponse } from 'next/server'

import { controlSessionSecret, verifyControlSession } from './lib/control-session'

export async function middleware(request: NextRequest) {
  const session = await verifyControlSession(
    request.cookies.get('control_session')?.value,
    controlSessionSecret(),
  )
  if (session) return NextResponse.next()
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
    '/api/operations/:path*',
  ],
}
