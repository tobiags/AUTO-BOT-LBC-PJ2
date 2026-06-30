import { Badge, Box, Flex, Heading, Table, Text } from '@radix-ui/themes'

import { CampaignStartButton } from '@/components/CampaignStartButton'
import { api, type Campaign } from '@/lib/api'

export const revalidate = 0

const STATUS_COLOR: Record<string, 'blue' | 'green' | 'orange' | 'gray' | 'red'> = {
  PENDING: 'gray',
  RUNNING: 'green',
  PAUSED: 'orange',
  COMPLETED: 'blue',
  FAILED: 'red',
}

export default async function CampaignsPage() {
  let campaigns: Campaign[] = []
  try {
    campaigns = await api.campaigns.list()
  } catch {
    // API indisponible
  }

  return (
    <Box>
      <Flex justify="between" align="center" mb="4">
        <Heading size="6">Campagnes</Heading>
        <Text size="2" color="gray">
          {campaigns.length} campagne(s)
        </Text>
      </Flex>

      <Table.Root variant="surface">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Type</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Envoyes</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Echoues</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Creee le</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Actions</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {campaigns.length === 0 ? (
            <Table.Row>
              <Table.Cell colSpan={6}>
                <Text color="gray">Aucune campagne</Text>
              </Table.Cell>
            </Table.Row>
          ) : (
            campaigns.map((campaign) => (
              <Table.Row key={campaign.id}>
                <Table.Cell>
                  <Text weight="bold" style={{ fontFamily: 'monospace', fontSize: 12 }}>
                    {campaign.type}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  <Badge color={STATUS_COLOR[campaign.status] ?? 'gray'}>{campaign.status}</Badge>
                </Table.Cell>
                <Table.Cell>
                  <Text color="green">{campaign.sent}</Text>
                </Table.Cell>
                <Table.Cell>
                  <Text color={campaign.failed > 0 ? 'red' : 'gray'}>{campaign.failed}</Text>
                </Table.Cell>
                <Table.Cell>
                  <Text size="2" color="gray">
                    {new Date(campaign.created_at).toLocaleDateString('fr-FR')}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  {campaign.status === 'PENDING' ? (
                    <CampaignStartButton campaignId={campaign.id} />
                  ) : (
                    <Text size="1" color="gray">
                      Aucune action
                    </Text>
                  )}
                </Table.Cell>
              </Table.Row>
            ))
          )}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}
