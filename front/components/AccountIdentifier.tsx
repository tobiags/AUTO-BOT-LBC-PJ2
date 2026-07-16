'use client'

import { Button, Flex, Text } from '@radix-ui/themes'
import { useState } from 'react'

type AccountIdentifierProps = {
  label: string
  value: string | null
}

export function AccountIdentifier({ label, value }: AccountIdentifierProps) {
  const [copied, setCopied] = useState(false)

  if (!value) {
    return <Text size="1" color="gray">Non attribue</Text>
  }

  async function copyValue() {
    if (!value) return
    await navigator.clipboard?.writeText(value)
    setCopied(true)
  }

  return (
    <Flex gap="2" align="center">
      <Text size="1" style={{ fontFamily: 'monospace' }}>{value}</Text>
      <Button
        size="1"
        variant="soft"
        onClick={copyValue}
        aria-label={`Copier ${label}`}
      >
        {copied ? 'Copie' : 'Copier'}
      </Button>
    </Flex>
  )
}
