'use client'

import { useState } from 'react'
import { Badge, Box, Button, Flex, Grid, Text } from '@radix-ui/themes'
import { RefreshCw, RotateCw } from 'lucide-react'

import type { DashboardConnector } from '@/lib/api'

const CONNECTORS = [
  ['database', 'PostgreSQL'],
  ['redis', 'Redis'],
  ['celery', 'Celery'],
  ['iproxy', 'iProxy 4G'],
  ['smstools', 'SMSTools'],
  ['smsapp', 'SmsApp'],
  ['mailgun', 'Mailgun'],
  ['browser_use', 'Browser Use Cloud'],
  ['camoufox', 'Camoufox'],
  ['obscura', 'Obscura'],
] as const

export function ConnectorControlPanel({ connectors }: { connectors: DashboardConnector[] }) {
  const [pending, setPending] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function runCommand(connector: string, action: 'probe' | 'rotate_ip') {
    setPending(`${connector}.${action}`)
    setMessage(null)
    try {
      const response = await fetch(`/api/operations/connectors/${connector}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      if (!response.ok) throw new Error('La commande a echoue')
      await response.json()
      setMessage('Commande terminee')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(null)
    }
  }

  return (
    <Box>
      {message && <Text size="2" as="div" mb="3" role="status">{message}</Text>}
      <Grid columns={{ initial: '1', md: '2' }} gap="3">
        {CONNECTORS.map(([name, label]) => {
          const connector = connectors.find((item) => item.name === name)
          const status = connector?.status ?? 'unverified'
          return (
            <Box key={name} p="3" style={{ border: '1px solid var(--gray-5)' }}>
              <Flex justify="between" align="center" gap="3" mb="2">
                <Text weight="bold">{label}</Text>
                <Badge color={status === 'ok' ? 'green' : status === 'down' ? 'red' : 'gray'}>
                  {status}
                </Badge>
              </Flex>
              <Text size="1" color="gray" as="div" mb="3">
                {connector?.latency_ms == null ? 'Latence inconnue' : `${connector.latency_ms} ms`}
              </Text>
              <Flex gap="2">
                <Button
                  size="1"
                  variant="soft"
                  disabled={pending !== null}
                  onClick={() => runCommand(name, 'probe')}
                  aria-label={`Tester ${label}`}
                  title={`Tester ${label}`}
                >
                  <RefreshCw size={14} /> Tester
                </Button>
                {name === 'iproxy' && (
                  <Button size="1" variant="outline" disabled title="Session admin requise">
                    <RotateCw size={14} /> Rotation IP
                  </Button>
                )}
              </Flex>
            </Box>
          )
        })}
      </Grid>
    </Box>
  )
}
