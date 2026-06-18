import { Badge, Box, Button, Flex, Heading, Table, Text } from '@radix-ui/themes'
import { api, type Campaign } from '@/lib/api'

export const revalidate = 0

const STATUS_COLOR: Record<string, 'blue' | 'green' | 'orange' | 'gray' | 'red'> = {
  PENDING: 'gray',
  RUNNING: 'green',
  PAUSED: 'orange',
  COMPLETED: 'blue',
  FAILED: 'red',
}

export default async function CampaignsPage() {
  let campaigns: Campaign[] = []
  try {
    campaigns = await api.campaigns.list()
  } catch {
    // API indisponible
  }

  return (
    <Box>
      <Flex justify="between" align="center" mb="4">
        <Heading size="6">Campagnes</Heading>
        <Text size="2" color="gray">
          {campaigns.length} campagne(s)
        </Text>
      </Flex>

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Nom</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Véhicule cible</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Budget max</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Années</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Actions</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {campaigns.length === 0 ? (
            <Table.Row>
              <Table.Cell colSpan={6}>
                <Text color="gray">Aucune campagne</Text>
              </Table.Cell>
            </Table.Row>
          ) : (
            campaigns.map((c) => (
              <Table.Row key={c.id}>
                <Table.Cell>
                  <Text weight="bold">{c.name}</Text>
                </Table.Cell>
                <Table.Cell>
                  {c.make} {c.model}
                </Table.Cell>
                <Table.Cell>
                  {c.price_max != null
                    ? `${c.price_max.toLocaleString('fr-FR')} €`
                    : '—'}
                </Table.Cell>
                <Table.Cell>
                  {c.year_min || c.year_max
                    ? `${c.year_min ?? '?'} – ${c.year_max ?? '?'}`
                    : '—'}
                </Table.Cell>
                <Table.Cell>
                  <Badge color={STATUS_COLOR[c.status] ?? 'gray'}>{c.status}</Badge>
                </Table.Cell>
                <Table.Cell>
                  <Flex gap="2">
                    {c.status === 'RUNNING' && (
                      <Button size="1" variant="soft" color="orange">
                        Pause
                      </Button>
                    )}
                    {c.status === 'PAUSED' && (
                      <Button size="1" variant="soft" color="green">
                        Reprendre
                      </Button>
                    )}
                  </Flex>
                </Table.Cell>
              </Table.Row>
            ))
          )}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
