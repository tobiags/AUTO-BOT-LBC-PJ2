'use client'

import { Button, Flex, Text } from '@radix-ui/themes'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export function EmailMessageControls({ messageId, unread }: { messageId: string; unread: boolean }) {
  const [feedback, setFeedback] = useState('')
  const [pending, setPending] = useState(false)
  const router = useRouter()

  async function run(action: 'read' | 'delete') {
    setPending(true)
    setFeedback('')
    const response = await fetch(`/api/operations/email-messages/${messageId}`, {
      method: action === 'delete' ? 'DELETE' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: action === 'read' ? JSON.stringify({ action }) : undefined,
    })
    if (response.ok) {
      setFeedback(action === 'read' ? 'Message marque comme lu.' : 'Message supprime.')
      router.refresh()
    } else if (response.status === 403) {
      setFeedback('Suppression reservee aux administrateurs.')
    } else {
      setFeedback('Operation impossible.')
    }
    setPending(false)
  }

  return <Flex gap="2" align="center" wrap="wrap">
    {unread && <Button size="1" disabled={pending} onClick={() => run('read')}>Marquer comme lu</Button>}
    <Button size="1" color="red" variant="soft" disabled={pending} onClick={() => run('delete')}>Supprimer</Button>
    {feedback && <Text size="1" role="status">{feedback}</Text>}
  </Flex>
}
