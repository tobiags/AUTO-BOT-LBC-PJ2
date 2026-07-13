import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

import { WorkspaceUsersControl } from '@/components/WorkspaceUsersControl'
import { controlSessionSecret, verifyControlSession } from '@/lib/control-session'

export default async function UsersPage() {
  const session = await verifyControlSession(
    (await cookies()).get('control_session')?.value,
    controlSessionSecret(),
  )
  if (!session) redirect('/login')
  return <WorkspaceUsersControl canCreate={session.role === 'admin'} />
}
