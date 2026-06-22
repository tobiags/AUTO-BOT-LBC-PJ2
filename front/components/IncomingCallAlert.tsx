'use client'
import { useState, useCallback } from 'react'
import { Badge, Box, Callout, Flex, Text } from '@radix-ui/themes'
import { useIncomingCalls, type IncomingCall } from '@/lib/websocket'

export function IncomingCallAlert() {
  const [calls, setCalls] = useState<IncomingCall[]>([])

  const handleCall = useCallback((call: IncomingCall) => {
    setCalls((prev) => [call, ...prev].slice(0, 5))
  }, [])

  const { connected } = useIncomingCalls(handleCall)

  return (
    <Box mb="4">
      <Flex align="center" gap="2" mb="2">
        <Badge color={connected ? 'green' : 'gray'} variant="soft">
          {connected ? 'Temps réel connecté' : 'Déconnecté'}
        </Badge>
      </Flex>
      {calls.map((call, i) => (
        <Callout.Root key={`${call.caller}-${i}`} color="green" mb="2">
          <Callout.Text>
            <strong>Appel entrant</strong> —{' '}
            <Text as="span" style={{ fontFamily: 'monospace' }}>
              {call.caller}
            </Text>
            {!!call.listing?.make && (
              <> · {String(call.listing.make)} {String(call.listing.model ?? '')}</>
            )}
            {!!call.listing?.price && (
              <> · {Number(call.listing.price).toLocaleString('fr-FR')} €</>
            )}
          </Callout.Text>
        </Callout.Root>
      ))}
    </Box>
  )
}
