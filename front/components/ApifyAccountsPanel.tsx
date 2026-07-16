'use client'

import { FormEvent, useState } from 'react'
import { Badge, Box, Button, Flex, Heading, Text, TextField } from '@radix-ui/themes'

import type { ApifyAccount } from '@/lib/apify-api'

export function ApifyAccountsPanel({ initialAccounts }: { initialAccounts: ApifyAccount[] }) {
  const [accounts, setAccounts] = useState(initialAccounts)
  const [label, setLabel] = useState('')
  const [token, setToken] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setMessage(null)
    try {
      const response = await fetch('/api/apify/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label, token }),
      })
      if (!response.ok) throw new Error('Connexion Apify impossible')
      const account = (await response.json()) as ApifyAccount
      setAccounts((current) => [...current, account])
      setLabel('')
      setToken('')
      setMessage('Compte connecte')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(false)
    }
  }

  return (
    <Box p="4" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
      <Heading size="4" mb="3">Comptes Apify</Heading>
      <form onSubmit={submit}>
        <Flex direction={{ initial: 'column', md: 'row' }} gap="2" align="end">
          <label style={{ flex: 1 }}>
            <Text size="2" as="div" mb="1">Libelle du compte</Text>
            <TextField.Root value={label} onChange={(event) => setLabel(event.target.value)} required />
          </label>
          <label style={{ flex: 1 }}>
            <Text size="2" as="div" mb="1">Jeton Apify</Text>
            <TextField.Root
              type="password"
              autoComplete="off"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              required
            />
          </label>
          <Button type="submit" disabled={pending}>Connecter le compte</Button>
        </Flex>
      </form>
      {message && <Text role="status" size="2" as="div" mt="2">{message}</Text>}
      <Flex direction="column" gap="2" mt="4">
        {accounts.map((account) => (
          <Flex key={account.id} justify="between" align="center" gap="3">
            <Box>
              <Text weight="bold" as="div">{account.label}</Text>
              <Text size="1" color="gray">{account.username} · {account.token_masked}</Text>
            </Box>
            <Badge color={account.status === 'active' ? 'green' : 'orange'}>{account.status}</Badge>
          </Flex>
        ))}
      </Flex>
    </Box>
  )
}
