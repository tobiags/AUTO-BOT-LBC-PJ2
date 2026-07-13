'use client'

import { FormEvent, useState } from 'react'
import { Box, Button, Flex, Select, Text, TextArea, TextField } from '@radix-ui/themes'
import { Plus } from 'lucide-react'
import { useRouter } from 'next/navigation'

export function CampaignCreateControl() {
  const router = useRouter()
  const [type, setType] = useState('lbc_message')
  const [messageTemplate, setMessageTemplate] = useState('Bonjour, votre vehicule est-il toujours disponible ?')
  const [region, setRegion] = useState('')
  const [department, setDepartment] = useState('')
  const [budgetMin, setBudgetMin] = useState('')
  const [budgetMax, setBudgetMax] = useState('')
  const [yearMax, setYearMax] = useState('')
  const [mileageMax, setMileageMax] = useState('')
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
        body: JSON.stringify({
          type,
          message_template: messageTemplate,
          quota_per_sim: quota,
          search_criteria: {
            region: region || null,
            department: department || null,
            budget_min: budgetMin ? Number(budgetMin) : null,
            budget_max: budgetMax ? Number(budgetMax) : null,
            year_max: yearMax ? Number(yearMax) : null,
            mileage_max: mileageMax ? Number(mileageMax) : null,
          },
        }),
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
          <Box style={{ flex: 1, minWidth: 210 }}>
            <Text size="2" weight="bold" as="div" mb="1">Région</Text>
            <TextField.Root
              value={region}
              onChange={(event) => setRegion(event.target.value)}
              placeholder="Île-de-France"
              aria-label="Région"
            />
          </Box>
          <Box style={{ width: 150 }}>
            <Text size="2" weight="bold" as="div" mb="1">Département</Text>
            <TextField.Root value={department} onChange={(event) => setDepartment(event.target.value)} placeholder="75" aria-label="Département" />
          </Box>
          <Box style={{ width: 130 }}>
            <Text size="2" weight="bold" as="div" mb="1">Budget minimum</Text>
            <TextField.Root
              type="number"
              min="0"
              value={budgetMin}
              onChange={(event) => setBudgetMin(event.target.value)}
              aria-label="Budget minimum"
            />
          </Box>
          <Box style={{ width: 130 }}>
            <Text size="2" weight="bold" as="div" mb="1">Année max.</Text>
            <TextField.Root type="number" min="1900" max="2100" value={yearMax} onChange={(event) => setYearMax(event.target.value)} aria-label="Année maximale" />
          </Box>
          <Box style={{ width: 140 }}>
            <Text size="2" weight="bold" as="div" mb="1">Kilométrage max.</Text>
            <TextField.Root type="number" min="0" value={mileageMax} onChange={(event) => setMileageMax(event.target.value)} aria-label="Kilométrage maximal" />
          </Box>
          <Box style={{ width: 130 }}>
            <Text size="2" weight="bold" as="div" mb="1">Budget maximum</Text>
            <TextField.Root
              type="number"
              min="0"
              value={budgetMax}
              onChange={(event) => setBudgetMax(event.target.value)}
              aria-label="Budget maximum"
            />
          </Box>
          <Box>
            <Text size="2" weight="bold" as="div" mb="1">Canal</Text>
            <Select.Root value={type} onValueChange={setType}>
              <Select.Trigger aria-label="Canal de campagne" />
              <Select.Content>
                <Select.Item value="lbc_message">Messagerie LBC</Select.Item>
                <Select.Item value="sms_direct">SMS direct</Select.Item>
                <Select.Item value="both">LBC + SMS selon disponibilité</Select.Item>
              </Select.Content>
            </Select.Root>
          </Box>
          <Box style={{ flex: 1, minWidth: 280 }}>
            <Text size="2" weight="bold" as="div" mb="1">Message a envoyer</Text>
            <TextArea
              required
              value={messageTemplate}
              onChange={(event) => setMessageTemplate(event.target.value)}
              aria-label="Message a envoyer"
            />
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
