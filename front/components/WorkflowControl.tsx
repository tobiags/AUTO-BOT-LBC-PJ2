'use client'

import { useEffect, useState } from 'react'
import { Badge, Box, Button, Flex, Progress, Table, Text } from '@radix-ui/themes'
import { Pause, Play, RefreshCw, RotateCcw, X } from 'lucide-react'

type Workflow = {
  id: string
  workflow_type: string
  target_type: string | null
  target_id: string | null
  status: string
  progress_current: number
  progress_total: number | null
  batch_number: number
  batch_size: number | null
  checkpoint: Record<string, unknown> | null
  last_error: string | null
  initiated_by: string | null
  created_at: string
  updated_at: string
}

const ACCOUNT_CREATE_STAGES = [
  ['profile_created', 'Profil Browser Use créé'],
  ['session_created', 'Session navigateur créée'],
  ['email_task_running', 'Saisie de l’e-mail en cours'],
  ['email_task_verified', 'E-mail validé'],
  ['otp_task_running', 'Saisie du code OTP en cours'],
  ['otp_verified', 'OTP validé'],
  ['account_verified', 'Compte vérifié'],
  ['completed', 'Création terminée'],
] as const

function AccountCreationProgress({ workflow }: { workflow: Workflow }) {
  const checkpoint = workflow.checkpoint ?? {}
  const current = String(checkpoint.stage ?? 'pending')
  const lastStage = String(checkpoint.last_stage ?? '')
  const currentIndex = ACCOUNT_CREATE_STAGES.findIndex(([stage]) => stage === current)
  const visibleCurrentIndex = current === 'account_verification_running'
    ? ACCOUNT_CREATE_STAGES.findIndex(([stage]) => stage === 'account_verified')
    : currentIndex
  const failedIndex = workflow.status === 'FAILED'
    ? ACCOUNT_CREATE_STAGES.findIndex(([stage]) => stage === lastStage)
    : -1
  const providerOutput = typeof checkpoint.provider_output === 'string'
    ? checkpoint.provider_output
    : ''
  const providerStatus = typeof checkpoint.provider_status === 'string'
    ? checkpoint.provider_status
    : ''
  return (
    <Box mt="2">
      <Text size="1" weight="bold" as="div">Progression de création</Text>
      <Flex direction="column" gap="1" mt="1">
        {ACCOUNT_CREATE_STAGES.map(([stage, label], index) => {
          const complete = workflow.status === 'COMPLETED'
            || (visibleCurrentIndex >= 0 && index < visibleCurrentIndex)
            || (failedIndex >= 0 && index < failedIndex)
          const active = (stage === current || (current === 'account_verification_running' && stage === 'account_verified'))
            && workflow.status !== 'FAILED'
          const failed = workflow.status === 'FAILED' && index === failedIndex
          return (
            <Flex key={stage} align="center" gap="2">
              <Text size="1" color={failed ? 'red' : complete ? 'green' : active ? 'blue' : 'gray'}>
                {failed ? '✕' : complete ? '✓' : active ? '…' : '○'}
              </Text>
              <Text size="1" color={failed ? 'red' : active ? 'blue' : 'gray'}>{label}</Text>
            </Flex>
          )
        })}
      </Flex>
      {(providerStatus || providerOutput) && (
        <Text size="1" color="gray" as="div" mt="2">
          Fournisseur : {providerStatus || 'inconnu'}{providerOutput ? ` · ${providerOutput}` : ''}
        </Text>
      )}
      {workflow.last_error && (
        <Text size="1" color="red" as="div" mt="1">Blocage : {workflow.last_error}</Text>
      )}
    </Box>
  )
}

export function WorkflowControl() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    const response = await fetch('/api/operations/workflows', { cache: 'no-store' })
    if (!response.ok) throw new Error('Workflows indisponibles')
    setWorkflows(await response.json())
  }
  useEffect(() => {
    load().catch((reason) => setError(reason.message))
    const refresh = window.setInterval(() => {
      load().catch((reason) => setError(reason.message))
    }, 8000)
    return () => window.clearInterval(refresh)
  }, [])

  async function command(id: string, action: string) {
    if (action === 'cancel' && !window.confirm('Annuler ce workflow ?')) return
    setPending(id)
    setError(null)
    try {
      const response = await fetch(`/api/operations/workflows/${id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      if (!response.ok) throw new Error('Commande workflow impossible')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Erreur inconnue')
    } finally {
      setPending(null)
    }
  }

  return (
    <Box>
      <Flex justify="between" mb="3">
        <Text size="2" color="gray">{workflows.length} executions</Text>
        <Button size="1" variant="soft" onClick={() => load()} title="Actualiser">
          <RefreshCw size={14} />
        </Button>
      </Flex>
      {error && <Text role="alert" size="2" color="red" as="div" mb="3">{error}</Text>}
      <Table.Root variant="surface">
        <Table.Header><Table.Row>
          <Table.ColumnHeaderCell>Workflow</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Progression</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Checkpoint / erreur</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Actions</Table.ColumnHeaderCell>
        </Table.Row></Table.Header>
        <Table.Body>
          {workflows.length === 0 ? (
            <Table.Row><Table.Cell colSpan={5}>Aucun workflow</Table.Cell></Table.Row>
          ) : workflows.map((workflow) => {
            const total = workflow.progress_total ?? 0
            const percent = total ? Math.min(100, workflow.progress_current / total * 100) : 0
            return (
              <Table.Row key={workflow.id}>
                <Table.Cell>
                  <Text weight="bold" size="2" as="div">{workflow.workflow_type}</Text>
                  <Text size="1" color="gray" as="div">
                    {workflow.target_type}: {workflow.target_id ?? '-'} · lot {workflow.batch_number}
                  </Text>
                  <Text size="1" color="gray" as="div">
                    Dernière activité : {new Date(workflow.updated_at).toLocaleString('fr-FR')}
                  </Text>
                </Table.Cell>
                <Table.Cell style={{ minWidth: 150 }}>
                  <Progress value={percent} mb="1" />
                  <Text size="1">{workflow.progress_current}{total ? ` / ${total}` : ''}</Text>
                </Table.Cell>
                <Table.Cell><Badge>{workflow.status}</Badge></Table.Cell>
                <Table.Cell>
                  <Text size="1" color={workflow.last_error ? 'red' : 'gray'}>
                    {workflow.last_error ?? JSON.stringify(workflow.checkpoint ?? {}).slice(0, 180)}
                  </Text>
                  {workflow.workflow_type === 'account.create' && (
                    <AccountCreationProgress workflow={workflow} />
                  )}
                </Table.Cell>
                <Table.Cell>
                  <Flex gap="1" wrap="wrap">
                    {['PENDING', 'RUNNING'].includes(workflow.status) && (
                      <Button size="1" variant="soft" disabled={pending === workflow.id} onClick={() => command(workflow.id, 'pause')}>
                        <Pause size={13} /> Pause
                      </Button>
                    )}
                    {workflow.status === 'PAUSED' && (
                      <Button size="1" variant="soft" disabled={pending === workflow.id} onClick={() => command(workflow.id, 'resume')}>
                        <Play size={13} /> Reprendre
                      </Button>
                    )}
                    {['FAILED', 'CANCELLED'].includes(workflow.status) && (
                      <Button size="1" variant="soft" disabled={pending === workflow.id} onClick={() => command(workflow.id, 'retry')}>
                        <RotateCcw size={13} /> Relancer
                      </Button>
                    )}
                    {['PENDING', 'RUNNING', 'PAUSED'].includes(workflow.status) && (
                      <Button size="1" color="red" variant="soft" disabled={pending === workflow.id} onClick={() => command(workflow.id, 'cancel')}>
                        <X size={13} /> Annuler
                      </Button>
                    )}
                  </Flex>
                </Table.Cell>
              </Table.Row>
            )
          })}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
