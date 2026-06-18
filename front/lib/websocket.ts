'use client'
import { useEffect, useRef, useState } from 'react'

const WS_URL = process.env.NEXT_PUBLIC_API_WS_URL ?? 'ws://localhost:8000/ws/calls'

export type IncomingCall = {
  listing_id: string
  phone: string
  make: string
  model: string
  price: number
  received_at: string
}

export function useIncomingCalls(onCall: (call: IncomingCall) => void) {
  const [connected, setConnected] = useState(false)
  const onCallRef = useRef(onCall)
  onCallRef.current = onCall

  useEffect(() => {
    const ws = new WebSocket(WS_URL)

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data as string) as IncomingCall
        onCallRef.current(data)
      } catch {
        // malformed message — ignore
      }
    }

    return () => ws.close()
  }, [])

  return { connected }
}
