'use client'

import { useState } from 'react'
import { Button, Flex, Select, Text } from '@radix-ui/themes'
import { Eye, Flame, Plus, RotateCcw, ShieldAlert } from 'lucide-react'
import { useRouter } from 'next/navigation'

import type { AccountStatus } from '@/lib/api'

export function AccountCreateControl() {
  const [mode, setMode] = useState('A')
  const [pending, setPending] = useState(false)
  const router = useRouter()
  return (
    <Flex gap="2">
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
          const response = await fetch('/api/operations/accounts', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode }),
          })
          setPending(false)
          if (response.ok) router.refresh()
        }}
      >
        <Plus size={14} /> Creer un compte
      </Button>
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
