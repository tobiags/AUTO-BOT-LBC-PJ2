import { Badge, Box, Button, Flex, Heading, Table, Text } from '@radix-ui/themes'
import { api, type Listing } from '@/lib/api'
import { PriceScoreBadge } from '@/components/PriceScoreBadge'

export const revalidate = 0

const STATUS_COLOR: Record<string, 'blue' | 'green' | 'orange' | 'gray' | 'purple'> = {
  NOUVELLE: 'blue',
  'SMS_ENVOYÉ': 'orange',
  'RÉPONSE': 'green',
  'TRAITÉ': 'gray',
  'ARCHIVÉ': 'gray',
}

export default async function ListingsPage() {
  let listings: Listing[] = []
  try {
    listings = await api.listings.list({ limit: 50 })
  } catch {
    // API indisponible
  }

  return (
    <Box>
      <Flex justify="between" align="center" mb="4">
        <Heading size="6">Annonces</Heading>
        <Text size="2" color="gray">
          {listings.length} résultat(s)
        </Text>
      </Flex>

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Véhicule</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Prix</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Score</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Moy. marché</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Km</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Actions</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {listings.length === 0 ? (
            <Table.Row>
              <Table.Cell colSpan={7}>
                <Text color="gray">Aucune annonce disponible</Text>
              </Table.Cell>
            </Table.Row>
          ) : (
            listings.map((l) => (
              <Table.Row key={l.id}>
                <Table.Cell>
                  <Text weight="bold">
                    {l.make ?? '—'} {l.model ?? ''}
                  </Text>
                  {l.year && (
                    <Text size="1" color="gray">
                      {' '}
                      — {l.year}
                    </Text>
                  )}
                </Table.Cell>
                <Table.Cell>
                  {l.price != null ? `${l.price.toLocaleString('fr-FR')} €` : '—'}
                </Table.Cell>
                <Table.Cell>
                  <PriceScoreBadge score={l.price_score} />
                </Table.Cell>
                <Table.Cell>
                  {l.market_avg_price != null
                    ? `${l.market_avg_price.toLocaleString('fr-FR')} €`
                    : <Text color="gray">—</Text>}
                </Table.Cell>
                <Table.Cell>
                  {l.km != null ? `${l.km.toLocaleString('fr-FR')} km` : '—'}
                </Table.Cell>
                <Table.Cell>
                  <Badge color={STATUS_COLOR[l.status] ?? 'gray'}>{l.status}</Badge>
                </Table.Cell>
                <Table.Cell>
                  <Flex gap="1">
                    <Button size="1" variant="soft" asChild>
                      <a href={l.url} target="_blank" rel="noreferrer">
                        Voir
                      </a>
                    </Button>
                    {l.price_score === null && (
                      <Button size="1" variant="outline">
                        Analyser
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
