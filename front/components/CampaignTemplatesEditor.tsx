'use client'

import { Button, Flex, Select, Text, TextArea, TextField } from '@radix-ui/themes'
import { useEffect, useState } from 'react'

type Template = {
  id: string
  channel: 'sms' | 'lbc'
  step: number
  delay_days: number
  send_time: string
  variant_key: string
  body: string
  enabled: boolean
}

export function CampaignTemplatesEditor({ campaignId }: { campaignId: string }) {
  const [templates, setTemplates] = useState<Template[]>([])
  const [selected, setSelected] = useState('sms:0:a')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch(`/api/campaigns/${campaignId}/templates`).then(async (response) => {
      if (response.ok) setTemplates(await response.json())
    })
  }, [campaignId])

  const key = selected.split(':')
  const template = templates.find((item) => item.channel === key[0] && item.step === Number(key[1]) && item.variant_key === key[2])
  const draft = template ?? {
    id: '', channel: key[0] as 'sms' | 'lbc', step: Number(key[1]), variant_key: key[2], delay_days: Number(key[1]) * 7,
    send_time: '10:00', body: '', enabled: true,
  }

  function update(patch: Partial<Template>) {
    setTemplates((current) => [...current.filter((item) => !(item.channel === draft.channel && item.step === draft.step && item.variant_key === draft.variant_key)), { ...draft, ...patch }])
  }

  async function save() {
    setSaving(true)
    const response = await fetch(`/api/campaigns/${campaignId}/templates`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft),
    })
    if (response.ok) update(await response.json())
    setSaving(false)
  }

  return (
    <Flex direction="column" gap="2" mt="2">
      <Text size="2" weight="bold">Templates et cadence</Text>
      <Select.Root value={selected} onValueChange={setSelected}>
        <Select.Trigger />
        <Select.Content>
          <Select.Item value="sms:0">SMS initial</Select.Item>
          {Array.from({ length: 8 }, (_, index) => ['a', 'b'].map((variant) => <Select.Item key={`sms-${index}-${variant}`} value={`sms:${index}:${variant}`}>SMS {index === 0 ? 'initial' : `semaine ${index}`} · variante {variant.toUpperCase()}</Select.Item>))}
          {Array.from({ length: 3 }, (_, index) => ['a', 'b'].map((variant) => <Select.Item key={`lbc-${index}-${variant}`} value={`lbc:${index}:${variant}`}>LBC {index === 0 ? 'initial' : `relance ${index}`} · variante {variant.toUpperCase()}</Select.Item>))}
        </Select.Content>
      </Select.Root>
      <TextArea value={draft.body} placeholder="Message éditable. Variables : {title}, {url}" onChange={(event) => update({ body: event.target.value })} />
      <Flex gap="2" align="center">
        <TextField.Root type="number" min="0" value={draft.delay_days} onChange={(event) => update({ delay_days: Number(event.target.value) })} />
        <TextField.Root type="time" value={draft.send_time} onChange={(event) => update({ send_time: event.target.value })} />
        <Button onClick={save} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
      </Flex>
    </Flex>
  )
}
