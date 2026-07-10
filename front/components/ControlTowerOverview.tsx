'use client'

import { Badge, Box, Flex, Grid, Heading, Text } from '@radix-ui/themes'

import type { ConnectorState, DashboardStats } from '@/lib/api'

const STATUS_COLOR: Record<ConnectorState, string> = {
  disabled: '#6b7280',
  unverified: '#6b7280',
  ok: '#18794e',
  degraded: '#ad5700',
  down: '#b42318',
  misconfigured: '#b42318',
}

export function ControlTowerOverview({ stats }: { stats: DashboardStats }) {
  const actionsRequired = stats.actions_required ?? []
  const workflows = stats.workflows ?? []
  const connectors = stats.connectors ?? []
  const metrics = [
    ['Annonces collectees', stats.listings_total ?? 0, stats.listings_today ?? 0],
    ['Messages LBC envoyes', stats.lbc_messages_sent_total ?? 0, stats.lbc_messages_sent_today ?? 0],
    ['Messages LBC recus', stats.lbc_messages_received_total ?? 0, stats.lbc_messages_received_today ?? 0],
    ['Numeros extraits', stats.phones_extracted_total ?? 0, stats.phones_extracted_today ?? 0],
    ['SMS envoyes', stats.sms_sent_total ?? 0, stats.sms_sent_today ?? 0],
    ['SMS recus', stats.sms_received_total ?? 0, stats.sms_received_today ?? 0],
    ['Appels recus', stats.calls_total ?? 0, stats.calls_today ?? 0],
  ] as const

  return (
    <Box mb="5">
      {actionsRequired.length > 0 && (
        <Box
          mb="4"
          p="3"
          style={{
            border: '1px solid var(--orange-6)',
            borderLeft: '4px solid var(--orange-9)',
            background: 'var(--orange-2)',
          }}
        >
          <Heading size="3" mb="2">Actions requises</Heading>
          <Flex direction="column" gap="2">
            {actionsRequired.map((action) => (
              <Flex key={action.code} justify="between" gap="3" wrap="wrap">
                <Box style={{ minWidth: 0 }}>
                  <Text size="2" weight="bold" as="div">{action.title}</Text>
                  <Text
                    size="1"
                    color="gray"
                    as="div"
                    style={{ overflowWrap: 'anywhere' }}
                  >
                    {action.detail}
                  </Text>
                </Box>
                <Badge color={action.severity === 'critical' ? 'red' : 'orange'}>
                  {action.code.split('.').at(-1)}
                </Badge>
              </Flex>
            ))}
          </Flex>
        </Box>
      )}

      <Text size="3" weight="bold" as="div" mb="2">Activite</Text>
      <Grid columns={{ initial: '1', xs: '2', md: '4' }} gap="3" mb="5">
        {metrics.map(([label, total, today]) => (
          <Box key={label} p="3" style={{ border: '1px solid var(--gray-5)', minWidth: 0 }}>
            <Text size="2" color="gray" as="div">{label}</Text>
            <Text size="7" weight="bold" as="div">{total}</Text>
            <Text size="1" color="gray" as="div">+{today} aujourd&apos;hui</Text>
          </Box>
        ))}
      </Grid>

      <Text size="3" weight="bold" as="div" mb="2">Workflows</Text>
      <Box mb="5" style={{ borderTop: '1px solid var(--gray-5)' }}>
        {workflows.length === 0 && (
          <Box py="3">
            <Text size="2" color="gray" as="div">Aucun workflow actif</Text>
          </Box>
        )}
        {workflows.map((workflow) => (
          <Flex
            key={workflow.id}
            justify="between"
            gap="3"
            py="3"
            wrap="wrap"
            style={{ borderBottom: '1px solid var(--gray-5)' }}
          >
            <Box style={{ minWidth: 180 }}>
              <Text size="2" weight="bold" as="div">{workflow.workflow_type}</Text>
              <Text size="1" color="gray" as="div">
                Lot {workflow.batch_number} - {workflow.progress_current}
                {workflow.progress_total !== null ? ` / ${workflow.progress_total}` : ''}
              </Text>
            </Box>
            <Badge
              color={
                workflow.status === 'FAILED'
                  ? 'red'
                  : workflow.status === 'PAUSED'
                    ? 'orange'
                    : 'blue'
              }
            >
              {workflow.status}
            </Badge>
            {workflow.last_error && (
              <Text
                size="1"
                color="red"
                style={{ overflowWrap: 'anywhere', maxWidth: 360 }}
              >
                {workflow.last_error}
              </Text>
            )}
          </Flex>
        ))}
      </Box>

      <Text size="3" weight="bold" as="div" mb="2">Connecteurs et infrastructure</Text>
      <Grid columns={{ initial: '1', xs: '2', md: '4' }} gap="3">
        {connectors.map((connector) => (
          <Box key={connector.name} p="3" style={{ border: '1px solid var(--gray-5)', minWidth: 0 }}>
            <Flex justify="between" gap="2" align="center">
              <Text size="2" weight="bold">{connector.name}</Text>
              <Text size="1" weight="bold" style={{ color: STATUS_COLOR[connector.status] }}>
                {connector.status}
              </Text>
            </Flex>
            <Text size="1" color="gray" as="div" mt="1">
              {connector.latency_ms === null ? 'Latence inconnue' : `${connector.latency_ms} ms`}
            </Text>
            {connector.error_code && (
              <Text
                size="1"
                color="red"
                as="div"
                mt="1"
                style={{ overflowWrap: 'anywhere' }}
              >
                {connector.error_code}
              </Text>
            )}
          </Box>
        ))}
      </Grid>
    </Box>
  )
}
