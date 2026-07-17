'use client'

import { useMemo, useState } from 'react'
import { Badge, Box, Button, Card, Flex, Grid, Heading, Text, TextField } from '@radix-ui/themes'

import type {
  PhoneActivation,
  PhoneOperationsDashboard,
  SmsMessage,
} from '@/lib/phone-operations-api'

type Tab = 'numbers' | 'messages'

function expiryLabel(expiresAt: string) {
  const remaining = new Date(expiresAt).getTime() - Date.now()
  if (remaining <= 0) return 'Expiré'
  const minutes = Math.max(1, Math.ceil(remaining / 60_000))
  return `Expire dans ${minutes} min`
}

function replaceActivation(rows: PhoneActivation[], updated: PhoneActivation) {
  const exists = rows.some((row) => row.id === updated.id)
  return exists
    ? rows.map((row) => row.id === updated.id ? updated : row)
    : [updated, ...rows]
}

export function PhoneOperationsControlCenter({ initialData }: { initialData: PhoneOperationsDashboard }) {
  const [tab, setTab] = useState<Tab>('numbers')
  const [activations, setActivations] = useState(initialData.activations.items)
  const [messages, setMessages] = useState(initialData.messages.items)
  const [numberQuery, setNumberQuery] = useState('')
  const [messageQuery, setMessageQuery] = useState('')
  const [direction, setDirection] = useState('')
  const [country, setCountry] = useState('')
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)

  const filteredActivations = useMemo(() => {
    const query = numberQuery.trim().toLowerCase()
    if (!query) return activations
    return activations.filter((row) =>
      `${row.phone_e164} ${row.provider_order_id} ${row.country} ${row.status}`
        .toLowerCase()
        .includes(query),
    )
  }, [activations, numberQuery])

  async function reserve() {
    setBusy(true)
    setFeedback('')
    const response = await fetch('/api/phone-operations/activations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ country: country.trim() || null, service: 'leboncoin' }),
    })
    if (response.ok) {
      const activation = await response.json() as PhoneActivation
      setActivations((rows) => replaceActivation(rows, activation))
      setFeedback('Numero reserve')
    } else {
      setFeedback('Reservation impossible')
    }
    setBusy(false)
  }

  async function mutateActivation(id: string, action: 'refresh' | 'cancel') {
    setBusy(true)
    setFeedback('')
    const response = await fetch(`/api/phone-operations/activations/${id}/${action}`, {
      method: 'POST',
    })
    if (response.ok) {
      const activation = await response.json() as PhoneActivation
      setActivations((rows) => replaceActivation(rows, activation))
      setFeedback(action === 'cancel' ? 'Numero annule' : 'Etat actualise')
    } else {
      setFeedback('Action impossible')
    }
    setBusy(false)
  }

  async function filterMessages() {
    const params = new URLSearchParams({ limit: '100' })
    if (direction) params.set('direction', direction)
    if (messageQuery.trim()) params.set('query', messageQuery.trim())
    const response = await fetch(`/api/phone-operations/messages?${params}`)
    if (response.ok) {
      const data = await response.json() as { items: SmsMessage[] }
      setMessages(data.items)
      setFeedback('Historique actualise')
    } else {
      setFeedback('Historique indisponible')
    }
  }

  const exportParams = new URLSearchParams()
  if (direction) exportParams.set('direction', direction)
  if (messageQuery.trim()) exportParams.set('query', messageQuery.trim())
  const exportHref = `/api/phone-operations/messages.csv${exportParams.size ? `?${exportParams}` : ''}`
  const metrics = [
    ['Numéros actifs', initialData.summary.active_numbers],
    ['OTP reçus', initialData.summary.received_numbers],
    ['SMS envoyés', initialData.summary.sms_sent],
    ['SMS reçus', initialData.summary.sms_received],
    ['Échecs SMS', initialData.summary.sms_failed],
  ] as const

  return (
    <Box>
      <Grid columns={{ initial: '2', md: '5' }} gap="3" mb="5">
        {metrics.map(([label, value]) => (
          <Card key={label}><Text size="1" color="gray" as="div">{label}</Text><Heading size="5">{value}</Heading></Card>
        ))}
      </Grid>
      <Flex role="tablist" aria-label="Sections téléphonie" gap="2" mb="4">
        <Button variant={tab === 'numbers' ? 'solid' : 'soft'} role="tab" aria-selected={tab === 'numbers'} onClick={() => setTab('numbers')}>Numéros temporaires</Button>
        <Button variant={tab === 'messages' ? 'solid' : 'soft'} role="tab" aria-selected={tab === 'messages'} onClick={() => setTab('messages')}>Historique SMS</Button>
      </Flex>

      {tab === 'numbers' && <Box role="tabpanel">
        <Card mb="4">
          <Heading size="4" mb="2">Réservation manuelle</Heading>
          <Text size="2" color="gray" as="div" mb="3">Laissez le pays vide pour utiliser le repli automatique configuré.</Text>
          <Flex gap="2" wrap="wrap">
            <TextField.Root aria-label="Pays du numéro" value={country} onChange={(event) => setCountry(event.target.value)} placeholder="france" />
            <Button disabled={busy} onClick={() => void reserve()}>Reserver un numero</Button>
          </Flex>
        </Card>
        <TextField.Root mb="3" aria-label="Rechercher un numéro" value={numberQuery} onChange={(event) => setNumberQuery(event.target.value)} placeholder="Numéro, commande, pays ou statut" />
        <Grid columns={{ initial: '1', lg: '2' }} gap="3">
          {filteredActivations.map((row) => (
            <Card key={row.id}>
              <Flex justify="between" align="start" gap="2">
                <Box>
                  <Heading size="4">{row.phone_e164}</Heading>
                  <Text size="1" color="gray">{row.country} · {row.service} · {row.origin}</Text>
                </Box>
                <Badge>{row.status}</Badge>
              </Flex>
              <Text size="2" as="div" mt="3">{expiryLabel(row.expires_at)}</Text>
              <Text size="1" color="gray" as="div">Commande {row.provider_order_id} · {row.cost.toFixed(2)} €</Text>
              {row.received_code && <Text size="5" weight="bold" as="div" mt="3">Code {row.received_code}</Text>}
              {row.received_sms && <Text size="2" as="div" mt="2">{row.received_sms}</Text>}
              {row.last_error && <Text size="1" color="red" as="div" mt="2">{row.last_error}</Text>}
              <Flex gap="2" mt="3">
                <Button size="1" variant="soft" disabled={busy} onClick={() => void mutateActivation(row.id, 'refresh')}>Actualiser</Button>
                {['reserved', 'waiting', 'received'].includes(row.status) && <Button size="1" color="red" variant="soft" disabled={busy} onClick={() => void mutateActivation(row.id, 'cancel')}>Annuler</Button>}
                <Button size="1" variant="ghost" onClick={() => void navigator.clipboard?.writeText(row.phone_e164)}>Copier</Button>
              </Flex>
            </Card>
          ))}
          {filteredActivations.length === 0 && <Text color="gray">Aucun numéro temporaire.</Text>}
        </Grid>
      </Box>}

      {tab === 'messages' && <Box role="tabpanel">
        <Flex gap="2" wrap="wrap" mb="4">
          <TextField.Root aria-label="Rechercher dans les SMS" value={messageQuery} onChange={(event) => setMessageQuery(event.target.value)} placeholder="Téléphone ou contenu" />
          <select aria-label="Direction SMS" value={direction} onChange={(event) => setDirection(event.target.value)}>
            <option value="">Tous les sens</option><option value="outbound">Envoyés</option><option value="inbound">Reçus</option>
          </select>
          <Button onClick={() => void filterMessages()}>Filtrer</Button>
          <Button asChild variant="soft"><a href={exportHref}>Exporter CSV</a></Button>
        </Flex>
        <Flex direction="column" gap="3">
          {messages.map((message) => (
            <Card key={message.id}>
              <Flex justify="between" align="start" gap="2">
                <Box><Heading size="3">{message.phone_e164}</Heading><Text size="1" color="gray">{new Date(message.occurred_at).toLocaleString('fr-FR')} · {message.sim_id}</Text></Box>
                <Flex gap="2"><Badge>{message.direction === 'outbound' ? 'envoyé' : 'reçu'}</Badge><Badge color={message.status === 'failed' ? 'red' : 'gray'}>{message.status}</Badge></Flex>
              </Flex>
              <Text size="2" as="div" mt="3" style={{ whiteSpace: 'pre-wrap' }}>{message.body}</Text>
              <Text size="1" color="gray" as="div" mt="2">Étape {message.sequence_step ?? '—'} · {message.variant_key ?? 'sans variante'} · {message.cost_eur?.toFixed(3) ?? '—'} €</Text>
            </Card>
          ))}
          {messages.length === 0 && <Text color="gray">Aucun SMS correspondant.</Text>}
        </Flex>
      </Box>}
      {feedback && <Text role="status" size="2" mt="4" as="div">{feedback}</Text>}
    </Box>
  )
}
