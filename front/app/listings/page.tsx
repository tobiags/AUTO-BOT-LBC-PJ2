import { Badge, Box, Button, Flex, Heading, Table, Text } from '@radix-ui/themes'

import { AnalyzeListingButton } from '@/components/AnalyzeListingButton'
import { PriceScoreBadge } from '@/components/PriceScoreBadge'
import { api, type Listing } from '@/lib/api'

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
          {listings.length} resultat(s)
        </Text>
      </Flex>

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Vehicule</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Prix</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Score</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Moy. marche</Table.ColumnHeaderCell>
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
            listings.map((listing) => (
              <Table.Row key={listing.id}>
                <Table.Cell>
                  <Text weight="bold">
                    {listing.make ?? '-'} {listing.model ?? ''}
                  </Text>
                  {listing.year && (
                    <Text size="1" color="gray">
                      {' '}
                      - {listing.year}
                    </Text>
                  )}
                </Table.Cell>
                <Table.Cell>
                  {listing.price != null ? `${listing.price.toLocaleString('fr-FR')} EUR` : '-'}
                </Table.Cell>
                <Table.Cell>
                  <PriceScoreBadge score={listing.price_score} />
                </Table.Cell>
                <Table.Cell>
                  {listing.market_avg_price != null
                    ? `${listing.market_avg_price.toLocaleString('fr-FR')} EUR`
                    : <Text color="gray">-</Text>}
                </Table.Cell>
                <Table.Cell>
                  {listing.km != null ? `${listing.km.toLocaleString('fr-FR')} km` : '-'}
                </Table.Cell>
                <Table.Cell>
                  <Badge color={STATUS_COLOR[listing.status] ?? 'gray'}>{listing.status}</Badge>
                </Table.Cell>
                <Table.Cell>
                  <Flex gap="1">
                    <Button size="1" variant="soft" asChild>
                      <a href={listing.url} target="_blank" rel="noreferrer">
                        Voir
                      </a>
                    </Button>
                    {listing.price_score === null && <AnalyzeListingButton listingId={listing.id} />}
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
