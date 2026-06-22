import { Box, Card, Flex, Heading, Text } from '@radix-ui/themes'
import { api } from '@/lib/api'
import { IncomingCallAlert } from '@/components/IncomingCallAlert'

export const revalidate = 30

export default async function DashboardPage() {
  let listingsCount = 0
  let activeAccounts = 0
  let analyzerTotal = 0
  let pendingAnalysis = 0

  try {
    const [listings, accounts, stats] = await Promise.all([
      api.listings.list({ limit: 200 }),
      api.accounts.list(),
      api.analyzer.stats(),
    ])
    listingsCount = listings.length
    activeAccounts = accounts.filter(
      (a) => a.status === 'ACTIF' || a.status === 'EN_CHAUFFE',
    ).length
    analyzerTotal = stats.analyzed
    pendingAnalysis = stats.pending
  } catch {
    // API indisponible — affichage dégradé
  }

  return (
    <Box>
      <Heading size="6" mb="4">
        Tableau de bord
      </Heading>

      <IncomingCallAlert />

      <Flex gap="4" wrap="wrap">
        <Card style={{ flex: 1, minWidth: 180 }}>
          <Text size="2" color="gray" as="div" mb="1">
            Annonces collectées
          </Text>
          <Text size="8" weight="bold">
            {listingsCount}
          </Text>
        </Card>

        <Card style={{ flex: 1, minWidth: 180 }}>
          <Text size="2" color="gray" as="div" mb="1">
            Comptes actifs / chauffe
          </Text>
          <Text
            size="8"
            weight="bold"
            color={activeAccounts < 3 ? 'red' : undefined}
          >
            {activeAccounts}
          </Text>
          {activeAccounts < 3 && (
            <Text size="1" color="red">
              Pool insuffisant (min. 3)
            </Text>
          )}
        </Card>

        <Card style={{ flex: 1, minWidth: 180 }}>
          <Text size="2" color="gray" as="div" mb="1">
            Analyses effectuées
          </Text>
          <Text size="8" weight="bold">
            {analyzerTotal}
          </Text>
        </Card>

        <Card style={{ flex: 1, minWidth: 180 }}>
          <Text size="2" color="gray" as="div" mb="1">
            En attente d'analyse
          </Text>
          <Text
            size="8"
            weight="bold"
            color={pendingAnalysis > 10 ? 'orange' : undefined}
          >
            {pendingAnalysis}
          </Text>
        </Card>
      </Flex>
    </Box>
  )
}
