'use client'

import { Button, Card, Checkbox, Flex, Grid, Heading, Text, TextField } from '@radix-ui/themes'
import { useEffect, useState } from 'react'

type Sector = { id: string; name: string; source: string; region: string; department: string; radius_km: number; brand_model: string | null; daily_volume: number; status: string }
type Account = { id: string; email: string; status: string }
type Resources = { account_ids: string[]; proxy_ids: string[]; sim_ids: string[]; daily_limit_per_account: number; daily_limit_per_sim: number }

export function SectorsControl() {
  const [sectors, setSectors] = useState<Sector[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [resourceSector, setResourceSector] = useState<Sector | null>(null)
  const [proxyIds, setProxyIds] = useState('')
  const [simIds, setSimIds] = useState('')
  const [accountLimit, setAccountLimit] = useState('10')
  const [simLimit, setSimLimit] = useState('15')
  const [feedback, setFeedback] = useState('')

  async function load() {
    const [sectorResponse, resourceResponse] = await Promise.all([
      fetch('/api/workspace/sectors', { cache: 'no-store' }),
      fetch('/api/workspace/resources', { cache: 'no-store' }),
    ])
    if (sectorResponse.ok) setSectors(await sectorResponse.json())
    if (resourceResponse.ok) setAccounts((await resourceResponse.json()).accounts ?? [])
  }
  useEffect(() => { void load() }, [])

  async function createSector(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const response = await fetch('/api/workspace/sectors', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      name: form.get('name'), source: form.get('source'), region: form.get('region'), department: form.get('department'), radius_km: Number(form.get('radius_km') || 0), brand_model: form.get('brand_model') || null, mileage_max: form.get('mileage_max') ? Number(form.get('mileage_max')) : null, price_min: form.get('price_min') ? Number(form.get('price_min')) : null, price_max: form.get('price_max') ? Number(form.get('price_max')) : null, frequency_minutes: Number(form.get('frequency_minutes') || 60), schedule_start: form.get('schedule_start'), schedule_end: form.get('schedule_end'), daily_volume: Number(form.get('daily_volume') || 50),
    }) })
    if (!response.ok) { setFeedback('Création du secteur impossible.'); return }
    setFeedback('Secteur créé.'); event.currentTarget.reset(); await load()
  }

  async function saveResources() {
    if (!resourceSector) return
    const response = await fetch(`/api/workspace/sectors/${resourceSector.id}/resources`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account_ids: selected, proxy_ids: proxyIds.split(',').map((v) => v.trim()).filter(Boolean), sim_ids: simIds.split(',').map((v) => v.trim()).filter(Boolean), daily_limit_per_account: Number(accountLimit), daily_limit_per_sim: Number(simLimit) }) })
    setFeedback(response.ok ? 'Ressources et quotas enregistrés.' : 'Affectation impossible.')
  }

  async function editResources(sector: Sector) {
    setResourceSector(sector)
    const response = await fetch(`/api/workspace/sectors/${sector.id}/resources`, { cache: 'no-store' })
    if (!response.ok) return
    const data: Resources = await response.json()
    setSelected(data.account_ids); setProxyIds(data.proxy_ids.join(', ')); setSimIds(data.sim_ids.join(', ')); setAccountLimit(String(data.daily_limit_per_account)); setSimLimit(String(data.daily_limit_per_sim))
  }

  return <Flex direction="column" gap="5">
    <Heading size="6">Secteurs d’acquisition</Heading>
    <Card><form onSubmit={createSector}><Flex direction="column" gap="3"><Heading size="4">Créer un secteur</Heading><Grid columns={{ initial: '1', md: '2' }} gap="3"><TextField.Root name="name" placeholder="Nom du secteur" required /><select name="source" defaultValue="leboncoin"><option value="leboncoin">LeBonCoin</option><option value="la_centrale">La Centrale</option></select><TextField.Root name="region" placeholder="Région" required /><TextField.Root name="department" placeholder="Département" required /><TextField.Root name="radius_km" type="number" placeholder="Rayon (km)" /><TextField.Root name="brand_model" placeholder="Marque / modèle" /><TextField.Root name="mileage_max" type="number" placeholder="Kilométrage max" /><TextField.Root name="price_min" type="number" placeholder="Prix minimum" /><TextField.Root name="price_max" type="number" placeholder="Prix maximum" /><TextField.Root name="frequency_minutes" type="number" defaultValue="60" placeholder="Fréquence (minutes)" /><TextField.Root name="schedule_start" defaultValue="06:00" placeholder="Début (HH:MM)" /><TextField.Root name="schedule_end" defaultValue="22:00" placeholder="Fin (HH:MM)" /><TextField.Root name="daily_volume" type="number" defaultValue="50" placeholder="Volume quotidien" /></Grid><Button type="submit">Créer le secteur</Button>{feedback && <Text role="status">{feedback}</Text>}</Flex></form></Card>
    <Flex direction="column" gap="3">{sectors.map((sector) => <Card key={sector.id}><Flex justify="between" align="center" gap="3" wrap="wrap"><BoxInfo sector={sector} /><Button variant="soft" onClick={() => void editResources(sector)}>Ressources & quotas</Button></Flex></Card>)}</Flex>
    {resourceSector && <Card><Flex direction="column" gap="3"><Heading size="4">Ressources — {resourceSector.name}</Heading><Text size="2" color="gray">Sélectionne les comptes LBC. Les SIM et proxies peuvent être saisis comme identifiants séparés par des virgules.</Text>{accounts.map((account) => <Flex key={account.id} gap="2" align="center"><Checkbox checked={selected.includes(account.id)} onCheckedChange={(checked) => setSelected((current) => checked ? [...current, account.id] : current.filter((id) => id !== account.id))} /><Text>{account.email} ({account.status})</Text></Flex>)}<TextField.Root value={proxyIds} onChange={(e) => setProxyIds(e.target.value)} placeholder="Proxies autorisés : proxy-1, proxy-2" /><TextField.Root value={simIds} onChange={(e) => setSimIds(e.target.value)} placeholder="SIM autorisées : sim-1, sim-2" /><Grid columns="2" gap="3"><TextField.Root type="number" value={accountLimit} onChange={(e) => setAccountLimit(e.target.value)} placeholder="Quota / compte / jour" /><TextField.Root type="number" value={simLimit} onChange={(e) => setSimLimit(e.target.value)} placeholder="Quota / SIM / jour" /></Grid><Button onClick={() => void saveResources()}>Enregistrer l’affectation</Button></Flex></Card>}
  </Flex>
}

function BoxInfo({ sector }: { sector: Sector }) { return <div><Text weight="bold" as="div">{sector.name}</Text><Text size="2" color="gray">{sector.source} · {sector.region} · {sector.department} · {sector.daily_volume}/jour</Text></div> }
