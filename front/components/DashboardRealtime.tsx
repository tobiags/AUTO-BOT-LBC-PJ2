'use client'

import { useCallback, useEffect, useState } from 'react'
import { Badge, Box, Card, Flex, Heading, Text } from '@radix-ui/themes'
import { useRouter } from 'next/navigation'

import type { DashboardStats, ServiceBalance } from '@/lib/api'
import {
  incrementCallCounters,
  prependIncomingCall,
  upsertBalance,
} from '@/lib/dashboard-state'
import {
  type BackofficeEvent,
  type IncomingCallEvent,
  useBackofficeEvents,
} from '@/lib/websocket'
import { ControlTowerOverview } from '@/components/ControlTowerOverview'
import { IncomingCallAlert } from '@/components/IncomingCallAlert'
import { DashboardRefreshButton } from '@/components/DashboardRefreshButton'
import { CampaignCreateControl } from '@/components/CampaignCreateControl'

const SERVICE_ICONS: Record<string, string> = {
  smstools: 'SMS',
  iproxy: '4G',
  browseruse: 'WEB',
  anthropic: 'AI',
}

function daysUntil(isoDate: string | null): number | null {
  if (!isoDate) return null
  const diff = new Date(isoDate).getTime() - Date.now()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

function CreditCard({ b }: { b: ServiceBalance }) {
  const icon = SERVICE_ICONS[b.service] ?? 'EUR'
  const unknown = b.balance === null
  const low = b.is_low
  const isAnthropicCost = b.service === 'anthropic'
  const daysLeft = daysUntil(b.expires_at)
  const expiryWarning = daysLeft !== null && daysLeft <= 7
  const expiryUrgent = daysLeft !== null && daysLeft <= 3

  const borderColor = isAnthropicCost
    ? 'var(--blue-9)'
    : expiryUrgent
      ? 'var(--red-9)'
      : expiryWarning
        ? 'var(--orange-9)'
        : low
          ? 'var(--red-9)'
          : 'var(--green-9)'

  const lastSeen = b.last_updated
    ? new Date(b.last_updated).toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null

  const expiresLabel = b.expires_at
    ? new Date(b.expires_at).toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    : null

  return (
    <Card style={{ flex: 1, minWidth: 180, borderLeft: `3px solid ${borderColor}` }}>
      <Flex justify="between" align="center" mb="1">
        <Text size="2" weight="bold">
          {icon} {b.label}
        </Text>
        {isAnthropicCost && <Badge color="blue" radius="full">Cout cumule</Badge>}
        {!isAnthropicCost && expiryUrgent && <Badge color="red" radius="full">Expire bientot</Badge>}
        {!isAnthropicCost && expiryWarning && !expiryUrgent && (
          <Badge color="orange" radius="full">{daysLeft}j restants</Badge>
        )}
        {!isAnthropicCost && low && !expiryWarning && <Badge color="red" radius="full">Faible</Badge>}
        {!isAnthropicCost && !low && !unknown && !expiryWarning && <Badge color="green" radius="full">OK</Badge>}
        {!isAnthropicCost && unknown && <Badge color="gray" radius="full">Inconnu</Badge>}
      </Flex>

      <Text
        size="7"
        weight="bold"
        color={
          (low || expiryUrgent) && !isAnthropicCost
            ? 'red'
            : expiryWarning && !isAnthropicCost
              ? 'orange'
              : unknown
                ? 'gray'
                : undefined
        }
      >
        {unknown ? '-' : `${b.balance?.toFixed(2)} ${b.currency}`}
      </Text>

      {expiryUrgent && (
        <Text size="1" color="red" as="div" mt="1">
          Expire dans {daysLeft} jour{daysLeft !== 1 ? 's' : ''} ({expiresLabel}) - recharger iProxy
        </Text>
      )}
      {expiryWarning && !expiryUrgent && (
        <Text size="1" color="orange" as="div" mt="1">
          Expire le {expiresLabel} ({daysLeft} jours)
        </Text>
      )}
      {!expiryWarning && expiresLabel && (
        <Text size="1" color="gray" as="div" mt="1">
          Valide jusqu&apos;au {expiresLabel}
        </Text>
      )}
      {!isAnthropicCost && low && !expiryWarning && (
        <Text size="1" color="red" as="div" mt="1">
          Rechargement requis (seuil : {b.low_threshold} {b.currency})
        </Text>
      )}
      {isAnthropicCost && (
        <Text size="1" color="blue" as="div" mt="1">
          Depense estimee depuis le dernier redemarrage
        </Text>
      )}
      {lastSeen && (
        <Text size="1" color="gray" as="div" mt="1">
          Mis a jour : {lastSeen}
        </Text>
      )}
      {!lastSeen && !isAnthropicCost && (
        <Text size="1" color="gray" as="div" mt="1">
          Polling au demarrage - en attente
        </Text>
      )}
    </Card>
  )
}

export function DashboardRealtime({ initialStats }: { initialStats: DashboardStats | null }) {
  const [stats, setStats] = useState(initialStats)
  const [calls, setCalls] = useState<IncomingCallEvent[]>([])
  const router = useRouter()

  useEffect(() => {
    setStats(initialStats)
  }, [initialStats])

  useEffect(() => {
    const refresh = window.setInterval(() => router.refresh(), 10000)
    return () => window.clearInterval(refresh)
  }, [router])

  const handleEvent = useCallback((event: BackofficeEvent) => {
    if (event.event === 'incoming_call') {
      setCalls((prev) => prependIncomingCall(prev, event))
      setStats((prev) => (prev ? incrementCallCounters(prev) : prev))
      return
    }

    setStats((prev) => (
      prev
        ? {
            ...prev,
            balances: upsertBalance(prev.balances, event),
          }
        : prev
    ))
  }, [])

  const { connected } = useBackofficeEvents(handleEvent)

  const anyLowBalance = stats?.balances.some((b) => b.is_low) ?? false
  const anyExpiringSoon = stats?.balances.some((b) => {
    if (!b.expires_at) return false
    const days = Math.ceil((new Date(b.expires_at).getTime() - Date.now()) / 86400000)
    return days <= 7
  }) ?? false

  return (
    <Box>
      <Flex justify="between" align="center" mb="4" wrap="wrap" gap="2">
        <Box>
          <Heading size="6">Tableau de bord</Heading>
          {stats?.generated_at && (
            <Text size="1" color="gray">
              Donnees actualisees le {new Date(stats.generated_at).toLocaleString('fr-FR')}
            </Text>
          )}
        </Box>
        <DashboardRefreshButton />
      </Flex>

      <IncomingCallAlert calls={calls} connected={connected} />

      <CampaignCreateControl />

      {anyLowBalance && (
        <Card mb="3" style={{ background: 'var(--red-2)', border: '1px solid var(--red-6)' }}>
          <Flex align="center" gap="2">
            <Box>
              <Text size="3" weight="bold" color="red" as="div">
                Credit insuffisant sur un ou plusieurs services
              </Text>
              <Text size="2" color="red">
                Rechargez des que possible pour eviter toute interruption.
              </Text>
            </Box>
          </Flex>
        </Card>
      )}

      {anyExpiringSoon && (
        <Card mb="4" style={{ background: 'var(--orange-2)', border: '1px solid var(--orange-6)' }}>
          <Flex align="center" gap="2">
            <Box>
              <Text size="3" weight="bold" color="orange" as="div">
                Abonnement expirant dans moins de 7 jours
              </Text>
              <Text size="2" color="orange">
                Renouvelez l&apos;abonnement iProxy ou BrowserUse pour eviter toute coupure.
              </Text>
            </Box>
          </Flex>
        </Card>
      )}

      <Text size="3" weight="bold" as="div" mb="2">Credits et services</Text>
      <Flex gap="3" wrap="wrap" mb="5">
        {stats?.balances.map((b) => (
          <CreditCard key={b.service} b={b} />
        ))}
        {!stats && (
          <Card style={{ flex: 1 }}>
            <Text color="gray">Impossible de charger les donnees - API indisponible</Text>
          </Card>
        )}
      </Flex>

      {stats && <ControlTowerOverview stats={stats} />}

      <Text size="3" weight="bold" as="div" mb="2">Comptes et campagnes</Text>
      <Flex gap="3" wrap="wrap">
        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">Comptes LBC actifs</Text>
          <Text size="7" weight="bold" color={(stats?.accounts_active ?? 0) < 3 ? 'red' : undefined}>
            {stats?.accounts_active ?? 0}
            <Text size="3" color="gray"> / {stats?.accounts_total ?? 0}</Text>
          </Text>
          {(stats?.accounts_active ?? 0) < 3 && (
            <Text size="1" color="red" as="div">Pool insuffisant (min. 3)</Text>
          )}
          <Text size="1" color="gray" as="div" mt="1">
            Chauffe {stats?.accounts_warming ?? 0} / Ralentis {stats?.accounts_slowed ?? 0}
            {' / '}Bloques {stats?.accounts_blocked ?? 0} / Quarantaine {stats?.accounts_quarantined ?? 0}
          </Text>
        </Card>

        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">Campagnes en cours</Text>
          <Text size="7" weight="bold" color={(stats?.campaigns_running ?? 0) > 0 ? 'green' : 'gray'}>
            {stats?.campaigns_running ?? 0}
          </Text>
          {(stats?.campaigns_running ?? 0) === 0 && (
            <Text size="1" color="gray" as="div">Aucune campagne active</Text>
          )}
        </Card>
      </Flex>

      <Flex justify="between" align="center" mt="5" mb="2">
        <Text size="3" weight="bold">Activité récente</Text>
        <Text size="1" color="gray">Actualisation automatique toutes les 10 secondes</Text>
      </Flex>
      <Flex direction="column" gap="2">
        {(stats?.workflows ?? []).slice(0, 6).map((workflow) => (
          <Card key={workflow.id}>
            <Flex justify="between" align="start" gap="3" wrap="wrap">
              <Box>
                <Text size="2" weight="bold" as="div">{workflow.workflow_type}</Text>
                <Text size="1" color="gray" as="div">
                  Lot {workflow.batch_number} · mis à jour le{' '}
                  {new Date(workflow.updated_at).toLocaleString('fr-FR')}
                </Text>
              </Box>
              <Badge color={workflow.status === 'FAILED' ? 'red' : workflow.status === 'RUNNING' ? 'green' : 'gray'}>
                {workflow.status}
              </Badge>
            </Flex>
            <Text size="1" color={workflow.last_error ? 'red' : 'gray'} as="div" mt="2">
              {workflow.last_error ?? (
                workflow.progress_total
                  ? `Progression : ${workflow.progress_current} / ${workflow.progress_total}`
                  : 'Aucune erreur enregistrée'
              )}
            </Text>
          </Card>
        ))}
        {!stats?.workflows.length && (
          <Text size="2" color="gray">Aucune activité récente.</Text>
        )}
      </Flex>
    </Box>
  )
}
