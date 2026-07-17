import { Box, Heading, Text } from '@radix-ui/themes'

import { PhoneOperationsControlCenter } from '@/components/PhoneOperationsControlCenter'
import {
  emptyPhoneOperationsDashboard,
  fetchPhoneOperationsDashboard,
} from '@/lib/phone-operations-api'

export const dynamic = 'force-dynamic'

export default async function PhonesPage() {
  let dashboard = emptyPhoneOperationsDashboard
  try {
    dashboard = await fetchPhoneOperationsDashboard()
  } catch {
    // The controls remain available and will surface provider/backend failures.
  }
  return (
    <Box>
      <Heading size="6" mb="2">Téléphonie & SMS</Heading>
      <Text size="2" color="gray" as="div" mb="5">
        Numéros OTP temporaires, automatisation et historique SMS réunis au même endroit.
      </Text>
      <PhoneOperationsControlCenter initialData={dashboard} />
    </Box>
  )
}
