'use client'

import { FormEvent, useEffect, useState } from 'react'
import { Badge, Box, Button, Flex, Select, Table, Text, TextField } from '@radix-ui/themes'
import { FlaskConical, RefreshCw, Square } from 'lucide-react'

type LabRun = {
  workflow_id: string
  engine: string
  target_url: string | null
  status: string
  result: Record<string, unknown>
  last_error: string | null
  created_at: string
}

export function ExperimentalLabControl() {
  const [runs, setRuns] = useState<LabRun[]>([])
  const [engine, setEngine] = useState('camoufox')
  const [targetUrl, setTargetUrl] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function loadRuns() {
    const response = await fetch('/api/operations/lab/runs', { cache: 'no-store' })
    if (!response.ok) throw new Error('Laboratoire indisponible')
    setRuns(await response.json())
  }

  useEffect(() => { loadRuns().catch((error) => setMessage(error.message)) }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setMessage(null)
    try {
      const response = await fetch('/api/operations/lab/runs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engine, target_url: targetUrl }),
      })
      if (!response.ok) throw new Error('Diagnostic refuse ou moteur desactive')
      setMessage('Diagnostic ajoute a la file')
      await loadRuns()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(false)
    }
  }

  async function stop(workflowId: string) {
    setPending(true)
    try {
      await fetch(`/api/operations/lab/runs/${workflowId}/stop`, { method: 'POST' })
      await loadRuns()
    } finally {
      setPending(false)
    }
  }

  return (
    <Box>
      <form onSubmit={submit}>
        <Flex gap="3" align="end" wrap="wrap" mb="4">
          <Box>
            <Text size="2" weight="bold" as="div" mb="1">Moteur</Text>
            <Select.Root value={engine} onValueChange={setEngine}>
              <Select.Trigger aria-label="Moteur experimental" />
              <Select.Content>
                <Select.Item value="camoufox">Camoufox</Select.Item>
                <Select.Item value="obscura">Obscura</Select.Item>
                <Select.Item value="both">Comparer les deux</Select.Item>
              </Select.Content>
            </Select.Root>
          </Box>
          <Box style={{ flex: 1, minWidth: 260 }}>
            <Text size="2" weight="bold" as="div" mb="1">URL autorisee</Text>
            <TextField.Root
              required type="url" value={targetUrl} aria-label="URL de diagnostic"
              placeholder="https://www.leboncoin.fr/..."
              onChange={(event) => setTargetUrl(event.target.value)}
            />
          </Box>
          <Button disabled={pending || !targetUrl}><FlaskConical size={15} /> Tester</Button>
          <Button type="button" variant="soft" onClick={() => loadRuns()} title="Actualiser">
            <RefreshCw size={15} />
          </Button>
        </Flex>
      </form>
      {message && <Text role="status" size="2" as="div" mb="3">{message}</Text>}
      <Table.Root variant="surface">
        <Table.Header><Table.Row>
          <Table.ColumnHeaderCell>Moteur</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Cible</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Rapport</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell>
        </Table.Row></Table.Header>
        <Table.Body>
          {runs.length === 0 ? (
            <Table.Row><Table.Cell colSpan={5}>Aucun diagnostic</Table.Cell></Table.Row>
          ) : runs.map((run) => (
            <Table.Row key={run.workflow_id}>
              <Table.Cell><Text weight="bold">{run.engine}</Text></Table.Cell>
              <Table.Cell><Text size="1">{run.target_url}</Text></Table.Cell>
              <Table.Cell><Badge>{run.status}</Badge></Table.Cell>
              <Table.Cell>
                <Text size="1">{run.last_error ?? JSON.stringify(run.result).slice(0, 180)}</Text>
              </Table.Cell>
              <Table.Cell>
                {['PENDING', 'RUNNING'].includes(run.status) && (
                  <Button size="1" color="red" variant="soft" onClick={() => stop(run.workflow_id)}>
                    <Square size={13} /> Arreter
                  </Button>
                )}
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
