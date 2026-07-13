'use client'

import { Badge, Box, Heading, Table, Text } from '@radix-ui/themes'
import { useEffect, useState } from 'react'

type Event = { id: string; actor: string; role: string; action: string; target_type: string | null; target_id: string | null; result_status: string; created_at: string }

export function AuditEventsControl() {
  const [events, setEvents] = useState<Event[]>([])
  useEffect(() => { void (async () => { const response = await fetch('/api/workspace/audit', { cache: 'no-store' }); if (response.ok) setEvents(await response.json()) })() }, [])
  return <Box><Heading size="6" mb="2">Audit des actions utilisateur</Heading><Text size="2" color="gray" as="div" mb="4">Historique des actions administratives et opérateur, sans secrets ni mots de passe.</Text><Table.Root variant="surface"><Table.Header><Table.Row><Table.ColumnHeaderCell>Date</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Utilisateur</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Rôle</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Cible</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Résultat</Table.ColumnHeaderCell></Table.Row></Table.Header><Table.Body>{events.map((event) => <Table.Row key={event.id}><Table.Cell>{new Date(event.created_at).toLocaleString('fr-FR')}</Table.Cell><Table.Cell>{event.actor}</Table.Cell><Table.Cell>{event.role}</Table.Cell><Table.Cell>{event.action}</Table.Cell><Table.Cell>{event.target_type ?? '-'} {event.target_id ? `(${event.target_id.slice(0, 8)})` : ''}</Table.Cell><Table.Cell><Badge color={event.result_status === 'success' ? 'green' : 'red'}>{event.result_status}</Badge></Table.Cell></Table.Row>)}{events.length === 0 && <Table.Row><Table.Cell colSpan={6}><Text color="gray">Aucun événement d’audit.</Text></Table.Cell></Table.Row>}</Table.Body></Table.Root></Box>
}
