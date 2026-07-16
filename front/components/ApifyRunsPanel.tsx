'use client'

import { useState } from 'react'
import { Badge, Box, Button, Flex, Heading, Text } from '@radix-ui/themes'

import type { ApifyRun } from '@/lib/apify-api'

function duration(run: ApifyRun): string {
  if (!run.started_at || !run.finished_at) return 'en cours'
  const seconds = Math.max(0, Math.round((Date.parse(run.finished_at) - Date.parse(run.started_at)) / 1000))
  return `${seconds} s`
}

export function ApifyRunsPanel({ runs }: { runs: ApifyRun[] }) {
  const [message, setMessage] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)

  async function replay(run: ApifyRun) {
    setPending(run.id)
    setMessage(null)
    try {
      const response = await fetch(`/api/apify/runs/${run.id}/replay`, { method: 'POST' })
      if (!response.ok) throw new Error('Rejeu impossible')
      setMessage('Import relance')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(null)
    }
  }

  return (
    <Box>
      <Heading size="4" mb="3">Runs Apify</Heading>
      {message && <Text role="status" as="div" mb="3">{message}</Text>}
      <Flex direction="column" gap="3">
        {runs.map((run) => (
          <Box key={run.id} p="3" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
            <Flex justify="between" align="center" gap="3">
              <Box>
                <Text weight="bold" as="div">{run.apify_run_id}</Text>
                <Text size="1" color="gray" as="div">
                  Dataset {run.default_dataset_id ?? 'absent'} · Duree {duration(run)} · Cout {run.cost_usd == null ? 'inconnu' : `${run.cost_usd.toFixed(4)} USD`}
                </Text>
              </Box>
              <Badge color={run.status === 'SUCCEEDED' ? 'green' : run.status === 'FAILED' ? 'red' : 'blue'}>{run.status}</Badge>
            </Flex>
            <Text size="1" as="div" mt="2">
              Lus {run.items_read} · Importes {run.items_imported} · Ignores {run.items_ignored} · Exceptions {run.items_exception}
            </Text>
            {run.last_error && <Text size="1" color="red" as="div">{run.last_error}</Text>}
            {run.status === 'SUCCEEDED' && (
              <Button size="1" variant="soft" mt="2" disabled={pending !== null} onClick={() => replay(run)}>
                Rejouer import {run.apify_run_id}
              </Button>
            )}
          </Box>
        ))}
      </Flex>
    </Box>
  )
}
