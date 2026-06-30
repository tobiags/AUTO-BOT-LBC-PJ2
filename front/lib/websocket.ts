'use client'

import { useEffect, useRef, useState } from 'react'

const WS_URL = process.env.NEXT_PUBLIC_API_WS_URL ?? 'ws://localhost:8000/ws'

export type IncomingCallEvent = {
  event: 'incoming_call'
  caller: string
  listing: Record<string, unknown>
}

export type BalanceUpdateEvent = {
  event: 'balance_update'
  service: string
  label: string
  balance: number | null
  currency: string
  is_low: boolean
  low_threshold: number
  last_updated: string
  expires_at?: string | null
}

export type BackofficeEvent = IncomingCallEvent | BalanceUpdateEvent

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isIncomingCallEvent(value: unknown): value is IncomingCallEvent {
  return (
    isRecord(value) &&
    value.event === 'incoming_call' &&
    typeof value.caller === 'string' &&
    isRecord(value.listing)
  )
}

function isBalanceUpdateEvent(value: unknown): value is BalanceUpdateEvent {
  return (
    isRecord(value) &&
    value.event === 'balance_update' &&
    typeof value.service === 'string' &&
    typeof value.label === 'string' &&
    typeof value.currency === 'string' &&
    typeof value.is_low === 'boolean' &&
    typeof value.low_threshold === 'number' &&
    typeof value.last_updated === 'string'
  )
}

export function parseBackofficeEvent(raw: string): BackofficeEvent | null {
  try {
    const data = JSON.parse(raw) as unknown
    if (isIncomingCallEvent(data)) return data
    if (isBalanceUpdateEvent(data)) return data
    return null
  } catch {
    return null
  }
}

export function useBackofficeEvents(onEvent: (event: BackofficeEvent) => void) {
  const [connected, setConnected] = useState(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    const ws = new WebSocket(WS_URL)

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (e: MessageEvent) => {
      const data = parseBackofficeEvent(String(e.data))
      if (data) onEventRef.current(data)
    }

    return () => ws.close()
  }, [])

  return { connected }
}
