'use client'

import { useState } from 'react'
import { Button } from '@radix-ui/themes'
import { RefreshCw } from 'lucide-react'
import { useRouter } from 'next/navigation'

export function DashboardRefreshButton() {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  return (
    <Button
      size="1" variant="soft" disabled={pending} title="Actualiser le tableau de bord"
      onClick={() => {
        setPending(true)
        router.refresh()
        window.setTimeout(() => setPending(false), 700)
      }}
    >
      <RefreshCw size={14} /> Actualiser
    </Button>
  )
}
