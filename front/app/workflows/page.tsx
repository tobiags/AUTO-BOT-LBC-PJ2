import { Box, Heading, Text } from '@radix-ui/themes'

import { WorkflowControl } from '@/components/WorkflowControl'

export default function WorkflowsPage() {
  return (
    <Box>
      <Heading size="6" mb="2">Workflows</Heading>
      <Text size="2" color="gray" as="div" mb="5">
        Progression par lots, checkpoints, erreurs et commandes d&apos;execution.
      </Text>
      <WorkflowControl />
    </Box>
  )
}
