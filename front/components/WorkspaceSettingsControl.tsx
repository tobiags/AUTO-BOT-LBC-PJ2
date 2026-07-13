'use client'

import { Button, Card, Flex, Heading, Text, TextField } from '@radix-ui/themes'
import { useEffect, useState } from 'react'

type Setting = { key: string; value: Record<string, unknown>; updated_by: string | null; updated_at: string }

export function WorkspaceSettingsControl() {
  const [settings, setSettings] = useState<Setting[]>([])
  const [windowStart, setWindowStart] = useState('06:00')
  const [windowEnd, setWindowEnd] = useState('22:00')
  const [dailySmsLimit, setDailySmsLimit] = useState('100')
  const [feedback, setFeedback] = useState('')

  useEffect(() => { void (async () => { const response = await fetch('/api/workspace/settings', { cache: 'no-store' }); if (!response.ok) return; const rows: Setting[] = await response.json(); setSettings(rows); const schedule = rows.find((row) => row.key === 'global.schedule'); const limits = rows.find((row) => row.key === 'global.limits'); if (schedule) { setWindowStart(String(schedule.value.start ?? '06:00')); setWindowEnd(String(schedule.value.end ?? '22:00')) }; if (limits) setDailySmsLimit(String(limits.value.daily_sms_limit ?? '100')) })() }, [])

  async function save(key: string, value: Record<string, unknown>) {
    const response = await fetch('/api/workspace/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key, value }) })
    setFeedback(response.ok ? 'Paramètres enregistrés.' : 'Enregistrement refusé. Vérifie le rôle administrateur.')
    if (response.ok) { const row = await response.json(); setSettings((current) => [...current.filter((item) => item.key !== row.key), row]) }
  }

  return <Flex direction="column" gap="4"><Heading size="6">Paramètres globaux</Heading><Card><Flex direction="column" gap="3"><Heading size="4">Fenêtre opérationnelle</Heading><Text size="2" color="gray">Ces paramètres s’appliquent aux nouveaux secteurs et aux garde-fous de planification.</Text><Flex gap="3"><TextField.Root value={windowStart} onChange={(e) => setWindowStart(e.target.value)} placeholder="Début HH:MM" /><TextField.Root value={windowEnd} onChange={(e) => setWindowEnd(e.target.value)} placeholder="Fin HH:MM" /></Flex><Button onClick={() => void save('global.schedule', { start: windowStart, end: windowEnd })}>Enregistrer la fenêtre</Button></Flex></Card><Card><Flex direction="column" gap="3"><Heading size="4">Limites globales</Heading><TextField.Root type="number" value={dailySmsLimit} onChange={(e) => setDailySmsLimit(e.target.value)} placeholder="Limite SMS quotidienne" /><Button onClick={() => void save('global.limits', { daily_sms_limit: Number(dailySmsLimit) })}>Enregistrer les limites</Button></Flex></Card>{feedback && <Text role="status">{feedback}</Text>}<Text size="2" color="gray">{settings.length} paramètre(s) enregistré(s). Les secrets fournisseurs ne sont jamais affichés ici : ils restent dans Coolify.</Text></Flex>
}
