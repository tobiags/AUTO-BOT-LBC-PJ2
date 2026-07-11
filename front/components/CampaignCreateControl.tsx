'use client'

import { FormEvent, useState } from 'react'
import { Box, Button, Flex, Select, Text, TextArea, TextField } from '@radix-ui/themes'
import { Plus } from 'lucide-react'
import { useRouter } from 'next/navigation'

export function CampaignCreateControl() {
  const router = useRouter()
  const [type, setType] = useState('lbc_message')
  const [messageTemplate, setMessageTemplate] = useState('Bonjour, votre vehicule est-il toujours disponible ?')
  const [quota, setQuota] = useState(15)
  const [pending, setPending] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setFeedback(null)
    try {
      const response = await fetch('/api/operations/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, message_template: messageTemplate, quota_per_sim: quota }),
      })
      if (!response.ok) throw new Error('Creation de campagne impossible')
      setFeedback('Campagne creee. Elle traitera les annonces eligibles par lots apres demarrage.')
      router.refresh()
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Erreur inconnue')
    } finally {
      setPending(false)
    }
  }

  return (
    <Box mb="5" p="3" style={{ border: '1px solid var(--gray-5)' }}>
      <form onSubmit={submit}>
        <Flex gap="3" wrap="wrap" align="end">
          <Box>
            <Text size="2" weight="bold" as="div" mb="1">Canal</Text>
            <Select.Root value={type} onValueChange={setType}>
              <Select.Trigger aria-label="Canal de campagne" />
              <Select.Content>
                <Select.Item value="lbc_message">Messagerie LBC</Select.Item>
                <Select.Item value="sms_direct">SMS direct</Select.Item>
              </Select.Content>
            </Select.Root>
          </Box>
          <Box style={{ flex: 1, minWidth: 280 }}>
            <Text size="2" weight="bold" as="div" mb="1">Message</Text>
            <TextArea required value={messageTemplate} onChange={(event) => setMessageTemplate(event.target.value)} />
          </Box>
          <Box style={{ width: 110 }}>
            <Text size="2" weight="bold" as="div" mb="1">Quota</Text>
            <TextField.Root type="number" min="1" max="60" value={quota} onChange={(event) => setQuota(Number(event.target.value))} />
          </Box>
          <Button disabled={pending || !messageTemplate.trim()}><Plus size={15} /> Creer</Button>
        </Flex>
      </form>
      {feedback && <Text size="2" as="div" mt="2" role="status">{feedback}</Text>}
    </Box>
  )
}
