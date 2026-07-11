'use client'

import { useState } from 'react'
import { Button, Flex, Text } from '@radix-ui/themes'
import { Pause, Play, RefreshCw, X } from 'lucide-react'
import { useRouter } from 'next/navigation'

import type { CampaignStatus } from '@/lib/api'

const ACTIONS: Partial<Record<CampaignStatus, Array<{
  action: 'start' | 'pause' | 'resume' | 'cancel' | 'retry'
  label: string
  icon: typeof Play
  color?: 'red'
}>>> = {
  PENDING: [
    { action: 'start', label: 'Demarrer', icon: Play },
    { action: 'cancel', label: 'Annuler', icon: X, color: 'red' },
  ],
  RUNNING: [
    { action: 'pause', label: 'Pause', icon: Pause },
    { action: 'cancel', label: 'Annuler', icon: X, color: 'red' },
  ],
  PAUSED: [
    { action: 'resume', label: 'Reprendre', icon: Play },
    { action: 'cancel', label: 'Annuler', icon: X, color: 'red' },
  ],
  FAILED: [{ action: 'retry', label: 'Relancer', icon: RefreshCw }],
}

export function CampaignControls({ campaignId, status }: {
  campaignId: string
  status: CampaignStatus
}) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const actions = ACTIONS[status] ?? []

  async function command(action: string) {
    if (action === 'cancel' && !window.confirm('Annuler cette campagne ?')) return
    setPending(true)
    setError(null)
    try {
      const response = await fetch(`/api/operations/campaigns/${campaignId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      if (!response.ok) throw new Error('Commande impossible')
      router.refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Erreur inconnue')
    } finally {
      setPending(false)
    }
  }

  if (actions.length === 0) return <Text size="1" color="gray">Terminee</Text>

  return (
    <Flex gap="1" wrap="wrap">
      {actions.map(({ action, label, icon: Icon, color }) => (
        <Button
          key={action}
          size="1"
          variant="soft"
          color={color}
          disabled={pending}
          onClick={() => command(action)}
        >
          <Icon size={13} /> {label}
        </Button>
      ))}
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
  )
}
