import { Box, Heading, Text } from '@radix-ui/themes'

import { ApifyControlCenter } from '@/components/ApifyControlCenter'
import { emptyApifyDashboard, fetchApifyDashboard } from '@/lib/apify-api'

export const dynamic = 'force-dynamic'

export default async function ApifyPage() {
  let dashboard = emptyApifyDashboard
  try {
    dashboard = await fetchApifyDashboard()
  } catch {
    // Keep the control center usable while the backend is unavailable.
  }
  return (
    <Box>
      <Heading size="6" mb="2">Infrastructure Apify</Heading>
      <Text size="2" color="gray" as="div" mb="5">
        Comptes, Actors, automatisations et ingestion directe vers les sequences SMS.
      </Text>
      <ApifyControlCenter initialData={dashboard} />
    </Box>
  )
}
