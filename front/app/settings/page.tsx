import { Box, Heading, Text } from '@radix-ui/themes'
import { ConnectorControlPanel } from '@/components/ConnectorControlPanel'
import { WorkspaceSettingsControl } from '@/components/WorkspaceSettingsControl'
import { api, type DashboardStats } from '@/lib/api'

export default async function SettingsPage() {
  let stats: DashboardStats | null = null
  try { stats = await api.dashboard.stats() } catch { /* affiche les connecteurs non vérifiés */ }
  return <Box><Heading size="6" mb="2">Administration</Heading><Text size="2" color="gray" as="div" mb="5">Intégrations, diagnostics et paramètres globaux du workspace.</Text><WorkspaceSettingsControl /><Heading size="5" mt="6" mb="2">Intégrations</Heading><ConnectorControlPanel connectors={stats?.connectors ?? []} /></Box>
}
