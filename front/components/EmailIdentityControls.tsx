'use client'

import { Button, Flex, Select, Text } from '@radix-ui/themes'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export function EmailIdentityBatchControl() {
  const [count, setCount] = useState('10')
  const [feedback, setFeedback] = useState('')
  const [pending, setPending] = useState(false)
  const router = useRouter()

  async function generate() {
    setPending(true); setFeedback('')
    try {
      const response = await fetch('/api/operations/email-identities', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ count: Number(count) }) })
      if (!response.ok) throw new Error('Generation refusee : role administrateur et domaine Mailgun requis.')
      setFeedback(`${count} identites creees.`); router.refresh()
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Generation impossible.')
    } finally { setPending(false) }
  }

  return <Flex gap="2" align="center" wrap="wrap"><Select.Root value={count} onValueChange={setCount}><Select.Trigger aria-label="Taille du lot" /><Select.Content><Select.Item value="10">10 identites</Select.Item><Select.Item value="15">15 identites</Select.Item><Select.Item value="20">20 identites</Select.Item></Select.Content></Select.Root><Button disabled={pending} onClick={generate}>Generer le lot</Button>{feedback && <Text size="1" role="status">{feedback}</Text>}</Flex>
}

export function EmailIdentityControl({ id, status }: { id: string; status: string }) {
  const router = useRouter()
  const [feedback, setFeedback] = useState('')
  const action = status === 'available' ? 'reserve' : status === 'reserved' ? 'release' : 'disable'
  async function command() {
    const response = await fetch(`/api/operations/email-identities/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) })
    setFeedback(response.ok ? 'Etat mis a jour.' : 'Commande refusee.')
    if (response.ok) router.refresh()
  }
  return <Flex gap="1" align="center"><Button size="1" variant="soft" onClick={command}>{action === 'reserve' ? 'Reserver' : action === 'release' ? 'Liberer' : 'Desactiver'}</Button>{feedback && <Text size="1">{feedback}</Text>}</Flex>
}
