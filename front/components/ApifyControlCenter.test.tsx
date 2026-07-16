import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { mockApifyDashboard } from '@/tests/handlers'
import { ApifyControlCenter } from './ApifyControlCenter'

describe('ApifyControlCenter', () => {
  it('never renders a saved token and can submit a new account', async () => {
    render(<ApifyControlCenter initialData={mockApifyDashboard} />)
    expect(screen.queryByText('apify_api_secret')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Libelle du compte'), {
      target: { value: 'Secondaire' },
    })
    fireEvent.change(screen.getByLabelText('Jeton Apify'), {
      target: { value: 'apify_api_new' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Connecter le compte' }))
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Compte connecte'),
    )
  })

  it('requires campaign and scheduling authority before enabling a binding', () => {
    render(<ApifyControlCenter initialData={mockApifyDashboard} />)
    fireEvent.click(screen.getByRole('button', { name: 'Activer Example Actor' }))
    expect(screen.getByText('Selectionnez une campagne active')).toBeInTheDocument()
  })
})
