'use client'

import { useEffect, useState } from 'react'
import { Button, Flex, Select, Text } from '@radix-ui/themes'
import { Eye, Flame, Plus, RotateCcw, ShieldAlert } from 'lucide-react'
import { useRouter } from 'next/navigation'

import type { AccountStatus } from '@/lib/api'

export function AccountCreateControl() {
  const [mode, setMode] = useState('B')
  const [pending, setPending] = useState(false)
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null)
  const router = useRouter()

  useEffect(() => {
    if (!workflowId) return
    let active = true
    const refreshWorkflow = async () => {
      const response = await fetch('/api/operations/workflows', { cache: 'no-store' })
      if (!response.ok) return
      const workflows = await response.json() as Array<{
        id: string
        status: string
        checkpoint?: { stage?: string }
        last_error?: string | null
      }>
      const workflow = workflows.find((item) => item.id === workflowId)
      if (!active || !workflow) return
      setWorkflowStatus(workflow.status)
      const stage = workflow.checkpoint?.stage
      if (workflow.status === 'FAILED') {
        setFeedback({ kind: 'error', text: workflow.last_error ?? 'Création échouée' })
      } else if (workflow.status === 'COMPLETED') {
        setFeedback({ kind: 'success', text: 'Compte créé. Actualisation du pool…' })
        router.refresh()
      } else if (stage) {
        setFeedback({ kind: 'success', text: `Création en cours : ${stage}` })
      }
    }
    void refreshWorkflow()
    const timer = window.setInterval(() => void refreshWorkflow(), 3000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [router, workflowId])

  return (
    <Flex gap="2" align="center" wrap="wrap">
      <Select.Root value={mode} onValueChange={setMode}>
        <Select.Trigger aria-label="Mode de creation" />
        <Select.Content>
          <Select.Item value="A">Mode A - local 4G</Select.Item>
          <Select.Item value="B">Mode B - Browser Use</Select.Item>
        </Select.Content>
      </Select.Root>
      <Button
        disabled={pending}
        onClick={async () => {
          setPending(true)
          setFeedback(null)
          try {
            const response = await fetch('/api/operations/accounts', {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ mode }),
            })
            const payload = await response.json().catch(() => null)
            if (!response.ok) {
              const detail = payload?.detail?.message ?? payload?.error ?? 'Commande impossible'
              throw new Error(detail)
            }
            setWorkflowId(payload?.workflow_id ?? null)
            setWorkflowStatus('PENDING')
            setFeedback({
              kind: 'success',
              text: payload?.workflow_id
                ? `Création mise en file (${payload.workflow_id.slice(0, 8)}…).`
                : `Création ${mode} mise en file.`,
            })
            router.refresh()
          } catch (reason) {
            setFeedback({
              kind: 'error',
              text: reason instanceof Error ? reason.message : 'Erreur de lancement',
            })
          } finally {
            setPending(false)
          }
        }}
      >
        <Plus size={14} /> Creer un compte
      </Button>
      {feedback && (
        <Text size="1" color={feedback.kind === 'error' ? 'red' : 'green'} role="status">
          {feedback.text}{workflowStatus && workflowStatus !== 'COMPLETED' ? ` · ${workflowStatus}` : ''}
        </Text>
      )}
    </Flex>
  )
}

export function AccountControls({ accountId, status, hasProfile }: {
  accountId: string
  status: AccountStatus
  hasProfile: boolean
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  async function command(action: string) {
    if (action === 'quarantine' && !window.confirm('Mettre ce compte en quarantaine ?')) return
    setPending(true)
    setError(null)
    const response = await fetch(`/api/operations/accounts/${accountId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    })
    setPending(false)
    if (!response.ok) {
      setError('Commande impossible')
      return
    }
    router.refresh()
  }

  return (
    <Flex gap="1" wrap="wrap">
      {hasProfile && (
        <Button size="1" variant="soft" disabled={pending} onClick={() => command('inspect')}>
          <Eye size={13} /> Inspecter
        </Button>
      )}
      {(status === 'RALENTI' || status.startsWith('EN_CR')) && (
        <Button size="1" variant="soft" disabled={pending} onClick={() => command('warm')}>
          <Flame size={13} /> Chauffer
        </Button>
      )}
      {status === 'QUARANTAINE' || status.includes('BLOQU') ? (
        <Button size="1" variant="soft" disabled={pending} onClick={() => command('restore')}>
          <RotateCcw size={13} /> Restaurer
        </Button>
      ) : (
        <Button
          size="1" color="red" variant="soft" disabled={pending}
          onClick={() => command('quarantine')}
        >
          <ShieldAlert size={13} /> Quarantaine
        </Button>
      )}
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
  )
}
