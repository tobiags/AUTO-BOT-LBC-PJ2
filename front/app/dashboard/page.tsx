import { DashboardRealtime } from '@/components/DashboardRealtime'
import { api, type DashboardStats } from '@/lib/api'

export const revalidate = 30

export default async function DashboardPage() {
  let stats: DashboardStats | null = null

  try {
    stats = await api.dashboard.stats()
  } catch {
    // API indisponible
  }

  return <DashboardRealtime initialStats={stats} />
}
