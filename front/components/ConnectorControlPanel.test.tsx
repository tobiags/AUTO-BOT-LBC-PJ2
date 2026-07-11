import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { ConnectorControlPanel } from './ConnectorControlPanel'

const connector = {
  name: 'iproxy',
  status: 'ok' as const,
  configured: true,
  latency_ms: 120,
  last_success_at: '2026-07-11T01:00:00Z',
  last_checked_at: '2026-07-11T01:00:00Z',
  error_code: null,
  error_summary: null,
  details: null,
}

it('runs an iproxy probe from the control panel', async () => {
  const user = userEvent.setup()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ status: 'completed', detail: { status: 'ok' } }),
  }))

  render(<ConnectorControlPanel connectors={[connector]} />)
  await user.click(screen.getByRole('button', { name: 'Tester iProxy 4G' }))

  expect(fetch).toHaveBeenCalledWith(
    '/api/operations/connectors/iproxy',
    expect.objectContaining({ method: 'POST' }),
  )
  expect(await screen.findByText('Commande terminee')).toBeTruthy()
})
