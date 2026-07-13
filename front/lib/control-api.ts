import type { NextRequest } from 'next/server'

export function controlApiHeaders(request: NextRequest): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Control-Tower-Token': process.env.CONTROL_TOWER_TOKEN ?? '',
    'X-Operator-Role': request.headers.get('x-control-role') === 'manager' ? 'operator' : request.headers.get('x-control-role') ?? 'viewer',
    'X-Operator-Id': request.headers.get('x-control-user') ?? 'unknown',
  }
}
