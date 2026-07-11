'use client'

import { useEffect, useState } from 'react'
import { Badge, Box, Button, Flex, Table, Text } from '@radix-ui/themes'
import { RefreshCw } from 'lucide-react'

type Message = {
  id: string
  external_key: string
  listing_id: string | null
  account_id: string | null
  direction: 'inbound' | 'outbound'
  status: string
  preview: string | null
  phone_extracted: boolean
  error_code: string | null
  created_at: string
}

export function MessagingControl() {
  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  async function load() {
    const response = await fetch('/api/operations/messaging', { cache: 'no-store' })
    if (!response.ok) throw new Error('Historique indisponible')
    setMessages(await response.json())
  }
  useEffect(() => { load().catch((error) => setNotice(error.message)) }, [])

  async function sync() {
    setPending(true)
    setNotice(null)
    try {
      const response = await fetch('/api/operations/messaging/sync', { method: 'POST' })
      if (!response.ok) throw new Error('Synchronisation impossible')
      setNotice('Synchronisation ajoutee a la file')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(false)
    }
  }

  const inbound = messages.filter((message) => message.direction === 'inbound').length
  const outbound = messages.filter((message) => message.direction === 'outbound').length
  const phones = messages.filter((message) => message.phone_extracted).length

  return (
    <Box>
      <Flex gap="4" wrap="wrap" align="center" mb="4">
        <Text size="2">Envoyes : <strong>{outbound}</strong></Text>
        <Text size="2">Recus : <strong>{inbound}</strong></Text>
        <Text size="2">Numeros : <strong>{phones}</strong></Text>
        <Button size="2" variant="soft" disabled={pending} onClick={sync}>
          <RefreshCw size={14} /> Synchroniser l&apos;inbox
        </Button>
      </Flex>
      {notice && <Text role="status" size="2" as="div" mb="3">{notice}</Text>}
      <Table.Root variant="surface">
        <Table.Header><Table.Row>
          <Table.ColumnHeaderCell>Date</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Direction</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Apercu</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Telephone</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Erreur</Table.ColumnHeaderCell>
        </Table.Row></Table.Header>
        <Table.Body>
          {messages.length === 0 ? (
            <Table.Row><Table.Cell colSpan={6}>Aucun message journalise</Table.Cell></Table.Row>
          ) : messages.map((message) => (
            <Table.Row key={message.id}>
              <Table.Cell><Text size="1">{new Date(message.created_at).toLocaleString('fr-FR')}</Text></Table.Cell>
              <Table.Cell><Badge color={message.direction === 'inbound' ? 'blue' : 'green'}>{message.direction}</Badge></Table.Cell>
              <Table.Cell>{message.status}</Table.Cell>
              <Table.Cell><Text size="1">{message.preview ?? '-'}</Text></Table.Cell>
              <Table.Cell>{message.phone_extracted ? 'Extrait' : '-'}</Table.Cell>
              <Table.Cell><Text size="1" color="red">{message.error_code ?? '-'}</Text></Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
