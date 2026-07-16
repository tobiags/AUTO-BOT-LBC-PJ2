'use client'

import { useMemo, useState } from 'react'
import { Badge, Box, Flex, Heading, Text, TextField } from '@radix-ui/themes'

import type { ApifyBinding, ApifyItem, ApifyRun } from '@/lib/apify-api'

export function ApifyResultsPanel({
  items,
  runs,
  bindings,
}: {
  items: ApifyItem[]
  runs: ApifyRun[]
  bindings: ApifyBinding[]
}) {
  const [bindingId, setBindingId] = useState('all')
  const [runId, setRunId] = useState('all')
  const [status, setStatus] = useState('all')
  const [date, setDate] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 20
  const runById = useMemo(() => new Map(runs.map((run) => [run.id, run])), [runs])
  const filtered = items.filter((item) => {
    const run = runById.get(item.run_id)
    return (bindingId === 'all' || run?.binding_id === bindingId)
      && (runId === 'all' || item.run_id === runId)
      && (status === 'all' || item.status === status)
      && (!date || item.created_at.startsWith(date))
  })
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize)

  return (
    <Box>
      <Heading size="4" mb="3">Resultats et leads</Heading>
      <Flex gap="2" wrap="wrap" mb="4">
        <label>
          <Text size="1" as="div">Actor</Text>
          <select aria-label="Filtrer par Actor" value={bindingId} onChange={(event) => { setBindingId(event.target.value); setPage(0) }}>
            <option value="all">Tous</option>
            {bindings.map((binding) => <option key={binding.id} value={binding.id}>{binding.name}</option>)}
          </select>
        </label>
        <label>
          <Text size="1" as="div">Run</Text>
          <select aria-label="Filtrer par run" value={runId} onChange={(event) => { setRunId(event.target.value); setPage(0) }}>
            <option value="all">Tous</option>
            {runs.map((run) => <option key={run.id} value={run.id}>{run.apify_run_id}</option>)}
          </select>
        </label>
        <label>
          <Text size="1" as="div">Statut</Text>
          <select aria-label="Filtrer par statut" value={status} onChange={(event) => { setStatus(event.target.value); setPage(0) }}>
            <option value="all">Tous</option>
            {['imported', 'ignored', 'duplicate', 'exception'].map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>
          <Text size="1" as="div">Date</Text>
          <TextField.Root type="date" value={date} onChange={(event) => { setDate(event.target.value); setPage(0) }} />
        </label>
      </Flex>
      <Flex direction="column" gap="3">
        {visible.map((item) => {
          const normalized = item.normalized_payload ?? {}
          return (
            <Box key={item.id} p="3" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
              <Flex justify="between" gap="3">
                <Box>
                  <Text weight="bold" as="div">{String(normalized.title ?? `Item ${item.dataset_index}`)}</Text>
                  <Text as="div">{String(normalized.phone_e164 ?? 'Telephone indisponible')}</Text>
                  <Text size="1" color="gray" as="div">
                    {String(normalized.source_platform ?? 'source inconnue')} · confiance {item.confidence == null ? 'n/a' : Math.round(item.confidence * 100)} %
                  </Text>
                </Box>
                <Badge>{item.status}</Badge>
              </Flex>
              <Flex gap="3" mt="2" wrap="wrap">
                {item.contact_id && <a href={`/contacts?contact=${item.contact_id}`}>Contact</a>}
                {item.listing_id && <a href={`/listings?listing=${item.listing_id}`}>Annonce</a>}
                {item.sms_sequence_id && <Text size="1">Sequence {item.sms_sequence_id}</Text>}
              </Flex>
              <details>
                <summary>JSON brut et normalise</summary>
                <Text size="1" weight="bold" as="div">Normalise</Text>
                <pre>{JSON.stringify(item.normalized_payload, null, 2)}</pre>
                <Text size="1" weight="bold" as="div">Brut</Text>
                <pre>{JSON.stringify(item.raw_payload, null, 2)}</pre>
              </details>
            </Box>
          )
        })}
      </Flex>
      <Flex justify="between" mt="3">
        <button type="button" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>Page precedente</button>
        <Text size="1">{filtered.length} resultat(s)</Text>
        <button type="button" disabled={(page + 1) * pageSize >= filtered.length} onClick={() => setPage((value) => value + 1)}>Page suivante</button>
      </Flex>
    </Box>
  )
}
