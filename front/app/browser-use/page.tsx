import { Box, Heading, Text } from '@radix-ui/themes'

import { BrowserUseControl } from '@/components/BrowserUseControl'

export default function BrowserUsePage() {
  return (
    <Box>
      <Heading size="6" mb="2">Browser Use Cloud</Heading>
      <Text size="2" color="gray" as="div" mb="5">
        Taches supervisees, sessions, couts, resultats et fichiers.
      </Text>
      <BrowserUseControl />
    </Box>
  )
}
