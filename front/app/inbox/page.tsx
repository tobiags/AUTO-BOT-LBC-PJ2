import Link from 'next/link'
import { Badge, Box, Flex, Heading, Table, Text } from '@radix-ui/themes'
import { api, type EmailIdentity, type EmailMessagePage } from '@/lib/api'

export const dynamic = 'force-dynamic'

export default async function InboxPage({ searchParams }: { searchParams: Promise<{ identity_id?: string; q?: string; unread?: string }> }) {
  const filters = await searchParams
  let page: EmailMessagePage = { items: [], total: 0 }
  let identities: EmailIdentity[] = []
  try { page = await api.emailMessages.list({ identity_id: filters.identity_id, query: filters.q, unread_only: filters.unread === '1' }) } catch { /* API indisponible */ }
  try { identities = await api.emailIdentities.list() } catch { /* API indisponible */ }

  return <Box>
    <Heading size="6" mb="1">Boite de reception</Heading>
    <Text color="gray" size="2">Messages conserves sept jours. {page.total} message{page.total > 1 ? 's' : ''}.</Text>
    <Flex gap="3" wrap="wrap" mt="4" mb="4">
      <Link href="/inbox">Toutes les adresses</Link>
      <Link href={filters.unread === '1' ? '/inbox' : '/inbox?unread=1'}>{filters.unread === '1' ? 'Afficher tous les messages' : 'Messages non lus'}</Link>
      {identities.map((identity) => <Link key={identity.id} href={`/inbox?identity_id=${identity.id}`}>{identity.email}</Link>)}
    </Flex>
    <Table.Root variant="surface">
      <Table.Header><Table.Row><Table.ColumnHeaderCell>Destinataire</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Expediteur</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Objet</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Recu le</Table.ColumnHeaderCell></Table.Row></Table.Header>
      <Table.Body>{page.items.length === 0 ? <Table.Row><Table.Cell colSpan={4}><Text color="gray">Aucun message recu.</Text></Table.Cell></Table.Row> : page.items.map((message) => <Table.Row key={message.id}><Table.Cell><Text size="1">{message.recipient}</Text></Table.Cell><Table.Cell>{message.sender}</Table.Cell><Table.Cell><Link href={`/inbox/${message.id}`}>{message.subject || '(sans objet)'}</Link> {!message.read_at && <Badge ml="2" color="blue">Nouveau</Badge>}</Table.Cell><Table.Cell><Text size="1">{new Date(message.received_at).toLocaleString('fr-FR')}</Text></Table.Cell></Table.Row>)}</Table.Body>
    </Table.Root>
  </Box>
}
