'use client'

import { startTransition, useState } from 'react'
import { Button, Text } from '@radix-ui/themes'

import { api } from '@/lib/api'

type Props = {
  listingId: string
  onSuccess?: () => void
}

export function AnalyzeListingButton({ listingId, onSuccess }: Props) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    setPending(true)
    setError(null)
    try {
      await api.analyzer.run(listingId)
      startTransition(() => {
        if (onSuccess) {
          onSuccess()
          return
        }
        window.location.reload()
      })
    } catch {
      setError('Impossible de lancer l analyse.')
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <Button size="1" variant="outline" disabled={pending} onClick={handleClick}>
        {pending ? 'Analyse...' : 'Analyser'}
      </Button>
      {error && <Text size="1" color="red">{error}</Text>}
    </>
  )
}
