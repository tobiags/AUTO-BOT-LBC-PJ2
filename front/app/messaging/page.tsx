import { Box, Heading, Text } from '@radix-ui/themes'

import { MessagingControl } from '@/components/MessagingControl'

export default function MessagingPage() {
  return (
    <Box>
      <Heading size="6" mb="2">Messagerie Leboncoin</Heading>
      <Text size="2" color="gray" as="div" mb="5">
        Messages sortants, inbox synchronisee et numeros extraits.
      </Text>
      <MessagingControl />
    </Box>
  )
}
