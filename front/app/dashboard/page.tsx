import { Badge, Box, Card, Flex, Heading, Text } from '@radix-ui/themes'
import { api, type DashboardStats, type ServiceBalance } from '@/lib/api'
import { IncomingCallAlert } from '@/components/IncomingCallAlert'

export const revalidate = 30

// ── Icônes services ──────────────────────────────────────────────────────────
const SERVICE_ICONS: Record<string, string> = {
  smstools:   '📱',
  iproxy:     '🔌',
  browseruse: '🌐',
  anthropic:  '🤖',
}

// ── Composant carte crédit ───────────────────────────────────────────────────
function CreditCard({ b }: { b: ServiceBalance }) {
  const icon = SERVICE_ICONS[b.service] ?? '💳'
  const unknown = b.balance === null
  const low = b.is_low
  const lastSeen = b.last_updated
    ? new Date(b.last_updated).toLocaleDateString('fr-FR', {
        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    : null

  return (
    <Card style={{ flex: 1, minWidth: 180, borderLeft: low ? '3px solid var(--red-9)' : '3px solid var(--green-9)' }}>
      <Flex justify="between" align="center" mb="1">
        <Text size="2" weight="bold">{icon} {b.label}</Text>
        {low && <Badge color="red" radius="full">Faible</Badge>}
        {!low && !unknown && <Badge color="green" radius="full">OK</Badge>}
        {unknown && <Badge color="gray" radius="full">Inconnu</Badge>}
      </Flex>
      <Text size="7" weight="bold" color={low ? 'red' : unknown ? 'gray' : undefined}>
        {unknown ? '—' : `${b.balance?.toFixed(2)} ${b.currency}`}
      </Text>
      {low && (
        <Text size="1" color="red" as="div" mt="1">
          ⚠️ Rechargement requis (seuil : {b.low_threshold} {b.currency})
        </Text>
      )}
      {lastSeen && (
        <Text size="1" color="gray" as="div" mt="1">
          Dernière mise à jour : {lastSeen}
        </Text>
      )}
      {!lastSeen && (
        <Text size="1" color="gray" as="div" mt="1">
          Aucune donnée reçue
        </Text>
      )}
    </Card>
  )
}

// ── Composant stat activité ──────────────────────────────────────────────────
function StatCard({
  label, total, today, icon, alertWhen,
}: {
  label: string
  total: number
  today: number
  icon: string
  alertWhen?: boolean
}) {
  return (
    <Card style={{ flex: 1, minWidth: 160 }}>
      <Text size="2" color="gray" as="div" mb="1">{icon} {label}</Text>
      <Text size="7" weight="bold" color={alertWhen ? 'red' : undefined}>
        {total}
      </Text>
      <Text size="1" color="gray" as="div">
        +{today} aujourd'hui
      </Text>
    </Card>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────
export default async function DashboardPage() {
  let stats: DashboardStats | null = null

  try {
    stats = await api.dashboard.stats()
  } catch {
    // API indisponible
  }

  const anyLowBalance = stats?.balances.some((b) => b.is_low) ?? false

  return (
    <Box>
      <Heading size="6" mb="4">Tableau de bord</Heading>

      <IncomingCallAlert />

      {/* Alerte globale crédit faible */}
      {anyLowBalance && (
        <Card mb="4" style={{ background: 'var(--red-2)', border: '1px solid var(--red-6)' }}>
          <Flex align="center" gap="2">
            <Text size="4">⚠️</Text>
            <Box>
              <Text size="3" weight="bold" color="red" as="div">
                Crédit insuffisant sur un ou plusieurs services
              </Text>
              <Text size="2" color="red">
                Rechargez dès que possible pour éviter toute interruption de service.
              </Text>
            </Box>
          </Flex>
        </Card>
      )}

      {/* Section crédits */}
      <Text size="3" weight="bold" as="div" mb="2">💳 Crédits & Services</Text>
      <Flex gap="3" wrap="wrap" mb="5">
        {stats?.balances.map((b) => (
          <CreditCard key={b.service} b={b} />
        ))}
        {!stats && (
          <Card style={{ flex: 1 }}>
            <Text color="gray">Impossible de charger les données — API indisponible</Text>
          </Card>
        )}
      </Flex>

      {/* Section activité */}
      <Text size="3" weight="bold" as="div" mb="2">📊 Activité</Text>
      <Flex gap="3" wrap="wrap" mb="5">
        <StatCard
          label="Annonces collectées"
          icon="🚗"
          total={stats?.listings_total ?? 0}
          today={stats?.listings_today ?? 0}
        />
        <StatCard
          label="SMS envoyés"
          icon="📤"
          total={stats?.sms_sent_total ?? 0}
          today={stats?.sms_sent_today ?? 0}
        />
        <StatCard
          label="SMS reçus"
          icon="📥"
          total={stats?.sms_received_total ?? 0}
          today={stats?.sms_received_today ?? 0}
        />
        <StatCard
          label="Appels reçus"
          icon="📞"
          total={stats?.calls_total ?? 0}
          today={stats?.calls_today ?? 0}
        />
      </Flex>

      {/* Section comptes & campagnes */}
      <Text size="3" weight="bold" as="div" mb="2">⚙️ Comptes & Campagnes</Text>
      <Flex gap="3" wrap="wrap">
        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">👤 Comptes LBC actifs</Text>
          <Text size="7" weight="bold" color={
            (stats?.accounts_active ?? 0) < 3 ? 'red' : undefined
          }>
            {stats?.accounts_active ?? 0}
            <Text size="3" color="gray"> / {stats?.accounts_total ?? 0}</Text>
          </Text>
          {(stats?.accounts_active ?? 0) < 3 && (
            <Text size="1" color="red" as="div">Pool insuffisant (min. 3)</Text>
          )}
        </Card>

        <Card style={{ flex: 1, minWidth: 160 }}>
          <Text size="2" color="gray" as="div" mb="1">🎯 Campagnes en cours</Text>
          <Text size="7" weight="bold" color={
            (stats?.campaigns_running ?? 0) > 0 ? 'green' : 'gray'
          }>
            {stats?.campaigns_running ?? 0}
          </Text>
          {(stats?.campaigns_running ?? 0) === 0 && (
            <Text size="1" color="gray" as="div">Aucune campagne active</Text>
          )}
        </Card>
      </Flex>
    </Box>
  )
}
