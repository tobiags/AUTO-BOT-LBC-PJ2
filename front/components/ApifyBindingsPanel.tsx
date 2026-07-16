'use client'

import { useState } from 'react'
import { Badge, Box, Button, Flex, Heading, Text } from '@radix-ui/themes'

import type { ApifyBinding } from '@/lib/apify-api'

export function ApifyBindingsPanel({ initialBindings }: { initialBindings: ApifyBinding[] }) {
  const [bindings, setBindings] = useState(initialBindings)
  const [message, setMessage] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)

  async function enable(binding: ApifyBinding) {
    if (!binding.campaign_id) {
      setMessage('Selectionnez une campagne active')
      return
    }
    if (
      (binding.schedule_authority === 'internal' && binding.schedule_minutes == null) ||
      (binding.schedule_authority === 'apify' && binding.schedule_minutes != null)
    ) {
      setMessage("Configurez l'autorite de planification")
      return
    }
    setPending(binding.id)
    setMessage(null)
    try {
      const response = await fetch(`/api/apify/bindings/${binding.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: true }),
      })
      if (!response.ok) throw new Error("Activation de l'Actor impossible")
      const updated = (await response.json()) as ApifyBinding
      setBindings((current) => current.map((item) => item.id === updated.id ? updated : item))
      setMessage('Actor active')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(null)
    }
  }

  return (
    <Box p="4" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
      <Heading size="4" mb="3">Actors et Tasks</Heading>
      {message && <Text role="status" size="2" as="div" mb="3">{message}</Text>}
      <Flex direction="column" gap="3">
        {bindings.map((binding) => (
          <Box key={binding.id} p="3" style={{ background: 'var(--gray-2)' }}>
            <Flex justify="between" align="center" gap="3">
              <Box>
                <Text weight="bold" as="div">{binding.name}</Text>
                <Text size="1" color="gray" as="div">
                  {binding.resource_type} · {binding.schedule_authority}
                  {binding.schedule_minutes ? ` · ${binding.schedule_minutes} min` : ''}
                </Text>
                <Text size="1" color="gray" as="div">
                  Compte: {binding.account_id} · Campagne: {binding.campaign_id ?? 'non selectionnee'} · Secteur: {binding.sector_id ?? 'automatique'}
                </Text>
              </Box>
              <Flex align="center" gap="2">
                <Badge color={binding.enabled ? 'green' : 'gray'}>{binding.enabled ? 'actif' : 'inactif'}</Badge>
                {!binding.enabled && (
                  <Button
                    size="1"
                    disabled={pending !== null}
                    onClick={() => enable(binding)}
                  >
                    Activer {binding.name}
                  </Button>
                )}
              </Flex>
            </Flex>
            <Text size="1" color="gray" as="div" mt="2">
              Prochain run: {binding.next_run_at ?? 'non planifie'} · Webhook: {binding.webhook_id ?? 'absent'} · Profil: {binding.active_profile_id ?? 'par defaut'}
            </Text>
          </Box>
        ))}
      </Flex>
    </Box>
  )
}
