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

  it('masks phones for viewers and exposes run replay status', async () => {
    render(<ApifyControlCenter initialData={mockApifyDashboard} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Resultats' }))
    expect(screen.getByText('+33 ** ** ** 67 8')).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
    fireEvent.click(screen.getByRole('tab', { name: 'Runs' }))
    fireEvent.click(screen.getByRole('button', { name: 'Rejouer import run-1' }))
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Import relance'),
    )
  })

  it('shows keep and discard experiments without enabling SMS actions', () => {
    render(<ApifyControlCenter initialData={mockApifyDashboard} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Apprentissage' }))
    expect(screen.getByText('discard')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /envoyer sms/i })).not.toBeInTheDocument()
  })

  it('allows an admin to rollback a retired profile', async () => {
    render(<ApifyControlCenter initialData={mockApifyDashboard} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Apprentissage' }))
    const rollback = await screen.findByRole('button', { name: 'Restaurer profil 0' })
    fireEvent.click(rollback)
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Profil restaure'),
    )
  })
})
