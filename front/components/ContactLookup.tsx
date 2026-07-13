'use client'

import { Button, Card, Flex, Text, TextField } from '@radix-ui/themes'
import { useState } from 'react'

type Lookup = {
  phone_e164: string
  listings: Array<{ id: string; title: string | null; price: number | null; source: string; url: string }>
  calls: Array<{ called_at: string; result: string | null; notes: string | null }>
}

export function ContactLookup() {
  const [phone, setPhone] = useState('')
  const [result, setResult] = useState<Lookup | null>(null)
  const [error, setError] = useState('')

  async function search() {
    setError('')
    const response = await fetch(`/api/contacts/lookup?phone=${encodeURIComponent(phone)}`)
    if (!response.ok) {
      setResult(null)
      setError('Numéro invalide ou inconnu')
      return
    }
    setResult(await response.json())
  }

  return (
    <Card mb="5">
      <Text size="3" weight="bold" as="div" mb="2">Recherche vendeur / appel</Text>
      <Flex gap="2">
        <TextField.Root value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+33612345678" />
        <Button onClick={search}>Rechercher</Button>
      </Flex>
      {error && <Text color="red" size="2">{error}</Text>}
      {result && (
        <BoxResult result={result} />
      )}
    </Card>
  )
}

function BoxResult({ result }: { result: Lookup }) {
  const latest = result.listings[0]
  return (
    <Flex direction="column" gap="1" mt="3">
      <Text size="2">Numéro normalisé : {result.phone_e164}</Text>
      {latest && <Text size="2" weight="bold">Annonce prioritaire : {latest.title ?? latest.url} · {latest.price ?? 'Prix inconnu'} € · {latest.source}</Text>}
      <Text size="1" color="gray">{result.listings.length} annonce(s), {result.calls.length} appel(s) historique(s)</Text>
      {result.calls.slice(0, 3).map((call) => <Text key={call.called_at} size="1" color="gray">{new Date(call.called_at).toLocaleString('fr-FR')} · {call.result ?? 'À qualifier'}</Text>)}
    </Flex>
  )
}
