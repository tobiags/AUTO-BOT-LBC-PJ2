import { Box, Heading, Text } from '@radix-ui/themes'

import { ConnectorControlPanel } from '@/components/ConnectorControlPanel'
import { api, type DashboardStats } from '@/lib/api'

export const revalidate = 15

export default async function ConnectorsPage() {
  let stats: DashboardStats | null = null
  try {
    stats = await api.dashboard.stats()
  } catch {
    // The control surface remains available and shows unverified providers.
  }

  return (
    <Box>
      <Heading size="6" mb="2">Connecteurs</Heading>
      <Text size="2" color="gray" as="div" mb="5">
        Etat, diagnostics et commandes des services externes.
      </Text>
      <ConnectorControlPanel connectors={stats?.connectors ?? []} />
    </Box>
  )
}
