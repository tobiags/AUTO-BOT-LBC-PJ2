import { Badge, Box, Flex, Heading, Table, Text } from '@radix-ui/themes'
import { api, type PlatformAccount } from '@/lib/api'

export const revalidate = 30

const STATUS_COLOR: Record<
  string,
  'blue' | 'green' | 'orange' | 'gray' | 'red' | 'purple'
> = {
  'EN_CRÉATION': 'gray',
  'EN_CHAUFFE': 'orange',
  ACTIF: 'green',
  RALENTI: 'blue',
  'BLOQUÉ': 'red',
  QUARANTAINE: 'purple',
}

const TRUST_COLOR: Record<string, 'red' | 'orange' | 'green'> = {
  LOW: 'red',
  MEDIUM: 'orange',
  HIGH: 'green',
}

export default async function AccountsPage() {
  let accounts: PlatformAccount[] = []
  try {
    accounts = await api.accounts.list()
  } catch {
    // API indisponible
  }

  const actifCount = accounts.filter(
    (a) => a.status === 'ACTIF' || a.status === 'EN_CHAUFFE',
  ).length

  return (
    <Box>
      <Flex justify="between" align="center" mb="4">
        <Heading size="6">Pool de comptes LBC</Heading>
        <Flex gap="3" align="center">
          <Badge color={actifCount >= 3 ? 'green' : 'red'}>
            {actifCount} / 3 min. actifs
          </Badge>
          <Text size="2" color="gray">
            {accounts.length} total
          </Text>
        </Flex>
      </Flex>

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>ID</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Santé</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Quota</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Erreurs 24h</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>DataDome</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {accounts.length === 0 ? (
            <Table.Row>
              <Table.Cell colSpan={6}>
                <Text color="gray">Aucun compte dans le pool</Text>
              </Table.Cell>
            </Table.Row>
          ) : (
            accounts.map((a) => (
              <Table.Row key={a.id}>
                <Table.Cell>
                  <Text size="1" style={{ fontFamily: 'monospace' }} color="gray">
                    …{a.id.slice(-8)}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  <Badge color={STATUS_COLOR[a.status] ?? 'gray'}>{a.status}</Badge>
                </Table.Cell>
                <Table.Cell>
                  <Text
                    color={
                      a.score_sante >= 70
                        ? 'green'
                        : a.score_sante >= 40
                          ? 'orange'
                          : 'red'
                    }
                    weight="bold"
                  >
                    {a.score_sante}/100
                  </Text>
                </Table.Cell>
                <Table.Cell>{a.quota_actuel}</Table.Cell>
                <Table.Cell>
                  <Text color={a.erreurs_24h > 3 ? 'red' : 'gray'}>
                    {a.erreurs_24h}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  <Badge color={TRUST_COLOR[a.datadome_trust_level] ?? 'gray'}>
                    {a.datadome_trust_level}
                  </Badge>
                </Table.Cell>
              </Table.Row>
            ))
          )}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
