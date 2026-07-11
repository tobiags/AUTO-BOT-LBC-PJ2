'use client'

import { FormEvent, useEffect, useState } from 'react'
import { Badge, Box, Button, Flex, Select, Table, Text, TextField } from '@radix-ui/themes'
import { ExternalLink, Play, RefreshCw, Square } from 'lucide-react'

type BrowserTask = {
  workflow_id: string
  status: string
  template_id: string
  target_url: string | null
  provider_task_id: string | null
  session_id: string | null
  cost: number | null
  output: string | null
  output_files: Array<{ name?: string; url?: string }>
  last_error: string | null
  created_at: string
}

const TEMPLATES = [
  ['listing_diagnostic', 'Diagnostic annonce'],
  ['listing_enrichment', 'Enrichissement annonce'],
  ['messaging_assist', 'Assistance messagerie'],
  ['account_diagnostic', 'Diagnostic compte'],
] as const

export function BrowserUseControl() {
  const [tasks, setTasks] = useState<BrowserTask[]>([])
  const [templateId, setTemplateId] = useState<string>(TEMPLATES[0][0])
  const [targetUrl, setTargetUrl] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function loadTasks() {
    const response = await fetch('/api/operations/browser-use/tasks', { cache: 'no-store' })
    if (!response.ok) throw new Error('Historique Browser Use indisponible')
    setTasks(await response.json())
  }

  useEffect(() => {
    loadTasks().catch((error) => setMessage(error.message))
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setMessage(null)
    try {
      const response = await fetch('/api/operations/browser-use/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: templateId, target_url: targetUrl }),
      })
      if (!response.ok) throw new Error('Lancement Browser Use impossible')
      setTargetUrl('')
      setMessage('Tache Browser Use ajoutee a la file')
      await loadTasks()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(false)
    }
  }

  async function stop(workflowId: string) {
    setPending(true)
    try {
      const response = await fetch(`/api/operations/browser-use/tasks/${workflowId}/stop`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error('Arret impossible')
      await loadTasks()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(false)
    }
  }

  return (
    <Box>
      <form onSubmit={submit}>
        <Flex gap="3" wrap="wrap" align="end" mb="4">
          <Box>
            <Text size="2" weight="bold" as="div" mb="1">Modele</Text>
            <Select.Root value={templateId} onValueChange={setTemplateId}>
              <Select.Trigger aria-label="Modele Browser Use" />
              <Select.Content>
                {TEMPLATES.map(([value, label]) => (
                  <Select.Item key={value} value={value}>{label}</Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Box>
          <Box style={{ flex: 1, minWidth: 260 }}>
            <Text size="2" weight="bold" as="div" mb="1">URL cible</Text>
            <TextField.Root
              required
              type="url"
              value={targetUrl}
              onChange={(event) => setTargetUrl(event.target.value)}
              placeholder="https://www.leboncoin.fr/..."
              aria-label="URL cible"
            />
          </Box>
          <Button disabled={pending || !targetUrl}>
            <Play size={15} /> Lancer
          </Button>
          <Button type="button" variant="soft" onClick={() => loadTasks()} title="Actualiser">
            <RefreshCw size={15} />
          </Button>
        </Flex>
      </form>
      {message && <Text size="2" as="div" mb="3" role="status">{message}</Text>}

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Tache</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Cout</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Resultat</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Actions</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {tasks.length === 0 ? (
            <Table.Row><Table.Cell colSpan={5}>Aucune tache Browser Use</Table.Cell></Table.Row>
          ) : tasks.map((task) => (
            <Table.Row key={task.workflow_id}>
              <Table.Cell>
                <Text size="2" weight="bold" as="div">{task.template_id}</Text>
                <Text size="1" color="gray" as="div">{task.target_url}</Text>
              </Table.Cell>
              <Table.Cell><Badge>{task.status}</Badge></Table.Cell>
              <Table.Cell>{task.cost == null ? '-' : `$${task.cost.toFixed(2)}`}</Table.Cell>
              <Table.Cell>{task.last_error ?? task.output ?? '-'}</Table.Cell>
              <Table.Cell>
                <Flex gap="2">
                  {['PENDING', 'RUNNING'].includes(task.status) && (
                    <Button size="1" color="red" variant="soft" onClick={() => stop(task.workflow_id)}>
                      <Square size={13} /> Arreter
                    </Button>
                  )}
                  {task.output_files.map((file) => file.url && (
                    <Button key={file.url} size="1" variant="ghost" asChild>
                      <a href={file.url} target="_blank" rel="noreferrer" title={file.name ?? 'Fichier'}>
                        <ExternalLink size={13} />
                      </a>
                    </Button>
                  ))}
                </Flex>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
