import type { DashboardStats, ServiceBalance } from '@/lib/api'
import type { BalanceUpdateEvent, IncomingCallEvent } from '@/lib/websocket'

export function prependIncomingCall(
  calls: IncomingCallEvent[],
  event: IncomingCallEvent,
): IncomingCallEvent[] {
  return [event, ...calls].slice(0, 5)
}

export function upsertBalance(
  balances: ServiceBalance[],
  event: BalanceUpdateEvent,
): ServiceBalance[] {
  const nextBalance: ServiceBalance = {
    service: event.service,
    label: event.label,
    balance: event.balance,
    currency: event.currency,
    is_low: event.is_low,
    low_threshold: event.low_threshold,
    last_updated: event.last_updated,
    expires_at: event.expires_at ?? null,
  }

  const index = balances.findIndex((balance) => balance.service === event.service)
  if (index === -1) return [...balances, nextBalance]

  const next = [...balances]
  next[index] = nextBalance
  return next
}

export function incrementCallCounters(stats: DashboardStats): DashboardStats {
  return {
    ...stats,
    calls_total: stats.calls_total + 1,
    calls_today: stats.calls_today + 1,
  }
}
