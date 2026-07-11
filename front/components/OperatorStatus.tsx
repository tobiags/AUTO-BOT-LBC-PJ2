'use client'

import { useEffect, useState } from 'react'
import { Badge, Text } from '@radix-ui/themes'

export function OperatorStatus() {
  const [session, setSession] = useState<{ operator: string; role: string } | null>(null)
  useEffect(() => {
    fetch('/api/auth/session')
      .then((response) => response.ok ? response.json() : null)
      .then(setSession)
  }, [])
  if (!session) return null
  return (
    <Text size="1" color="gray" as="div">
      {session.operator} <Badge color={session.role === 'admin' ? 'red' : 'blue'}>{session.role}</Badge>
    </Text>
  )
}
