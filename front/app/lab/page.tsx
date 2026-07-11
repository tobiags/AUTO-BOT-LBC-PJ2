import { Box, Heading, Text } from '@radix-ui/themes'

import { ExperimentalLabControl } from '@/components/ExperimentalLabControl'

export default function LabPage() {
  return (
    <Box>
      <Heading size="6" mb="2">Laboratoire experimental</Heading>
      <Text size="2" color="gray" as="div" mb="5">
        Diagnostics isoles Camoufox et Obscura sur domaines autorises.
      </Text>
      <ExperimentalLabControl />
    </Box>
  )
}
