'use client'

import { startTransition, useState } from 'react'
import { Button, Text } from '@radix-ui/themes'

import { api } from '@/lib/api'

type Props = {
  campaignId: string
  onSuccess?: () => void
}

export function CampaignStartButton({ campaignId, onSuccess }: Props) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    setPending(true)
    setError(null)
    try {
      await api.campaigns.start(campaignId)
      startTransition(() => {
        if (onSuccess) {
          onSuccess()
          return
        }
        window.location.reload()
      })
    } catch {
      setError('Impossible de demarrer la campagne.')
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <Button size="1" variant="soft" color="green" disabled={pending} onClick={handleClick}>
        {pending ? 'Demarrage...' : 'Demarrer'}
      </Button>
      {error && <Text size="1" color="red">{error}</Text>}
    </>
  )
}
