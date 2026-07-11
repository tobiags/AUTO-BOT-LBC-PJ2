import { createControlSession, verifyControlSession } from './control-session'

it('signs and verifies an admin control session', async () => {
  const token = await createControlSession('operator@example.com', 'admin', 'test-secret')
  const session = await verifyControlSession(token, 'test-secret')

  expect(session?.sub).toBe('operator@example.com')
  expect(session?.role).toBe('admin')
})

it('rejects a modified control session', async () => {
  const token = await createControlSession('operator', 'operator', 'test-secret')

  expect(await verifyControlSession(`${token}x`, 'test-secret')).toBeNull()
})
