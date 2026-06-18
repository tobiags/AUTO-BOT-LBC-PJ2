import { Box, Card, Flex, Heading, Table, Text } from '@radix-ui/themes'
import { api, type AnalyzerResult, type AnalyzerStats } from '@/lib/api'
import { PriceScoreBadge } from '@/components/PriceScoreBadge'

export const revalidate = 0

const EMPTY_STATS: AnalyzerStats = {
  total_analyzed: 0,
  pending: 0,
  avg_score: null,
  high_value_count: 0,
}

export default async function AnalyzerPage() {
  let stats = EMPTY_STATS
  let results: AnalyzerResult[] = []

  try {
    ;[stats, results] = await Promise.all([
      api.analyzer.stats(),
      api.analyzer.results({ limit: 20 }),
    ])
  } catch {
    // API indisponible
  }

  return (
    <Box>
      <Heading size="6" mb="4">
        Analyste prix
      </Heading>

      <Flex gap="4" mb="6" wrap="wrap">
        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">
            Total analysés
          </Text>
          <Text size="7" weight="bold">
            {stats.total_analyzed}
          </Text>
        </Card>

        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">
            En attente
          </Text>
          <Text
            size="7"
            weight="bold"
            color={stats.pending > 10 ? 'orange' : undefined}
          >
            {stats.pending}
          </Text>
        </Card>

        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">
            Score moyen
          </Text>
          <Text size="7" weight="bold">
            {stats.avg_score != null ? stats.avg_score.toFixed(1) : '—'}
          </Text>
        </Card>

        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">
            Bonnes affaires (≥ 8)
          </Text>
          <Text size="7" weight="bold" color="green">
            {stats.high_value_count}
          </Text>
        </Card>
      </Flex>

      <Heading size="4" mb="3">
        Dernières analyses
      </Heading>
      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Score</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Moy. marché</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Échantillon</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Synthèse IA</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {results.length === 0 ? (
            <Table.Row>
              <Table.Cell colSpan={4}>
                <Text color="gray">Aucune analyse disponible</Text>
              </Table.Cell>
            </Table.Row>
          ) : (
            results.map((r) => (
              <Table.Row key={r.listing_id}>
                <Table.Cell>
                  <PriceScoreBadge score={r.price_score} />
                </Table.Cell>
                <Table.Cell>
                  {r.market_avg_price.toLocaleString('fr-FR')} €
                </Table.Cell>
                <Table.Cell>{r.market_sample_size} annonces</Table.Cell>
                <Table.Cell>
                  <Text
                    size="1"
                    style={{ maxWidth: 400, display: 'block' }}
                    title={r.ai_summary}
                  >
                    {r.ai_summary.length > 120
                      ? `${r.ai_summary.slice(0, 120)}…`
                      : r.ai_summary}
                  </Text>
                </Table.Cell>
              </Table.Row>
            ))
          )}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
