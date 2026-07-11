import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Theme } from '@radix-ui/themes'
import { AnalyzeListingButton } from '@/components/AnalyzeListingButton'
import { CampaignStartButton } from '@/components/CampaignStartButton'
import { CampaignCreateControl } from '@/components/CampaignCreateControl'
import { PriceScoreBadge } from '@/components/PriceScoreBadge'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}))

function Wrap({ children }: { children: React.ReactNode }) {
  return <Theme>{children}</Theme>
}

describe('PriceScoreBadge', () => {
  it('affiche un tiret pour un score null', () => {
    render(<Wrap><PriceScoreBadge score={null} /></Wrap>)
    expect(screen.getByText('—')).toBeTruthy()
  })

  it('affiche le score ≥ 8 (bonne affaire)', () => {
    render(<Wrap><PriceScoreBadge score={8.5} /></Wrap>)
    expect(screen.getByText('8.5/10')).toBeTruthy()
  })

  it('affiche le score entre 6 et 7.9 (correct)', () => {
    render(<Wrap><PriceScoreBadge score={6.5} /></Wrap>)
    expect(screen.getByText('6.5/10')).toBeTruthy()
  })

  it('affiche le score < 6 (mauvaise affaire)', () => {
    render(<Wrap><PriceScoreBadge score={3} /></Wrap>)
    expect(screen.getByText('3/10')).toBeTruthy()
  })

  it('affiche le score exact 8 comme bonne affaire', () => {
    render(<Wrap><PriceScoreBadge score={8} /></Wrap>)
    expect(screen.getByText('8/10')).toBeTruthy()
  })
})

describe('CampaignStartButton', () => {
  it('declenche le demarrage de campagne puis appelle onSuccess', async () => {
    const user = userEvent.setup()
    const onSuccess = vi.fn()

    render(
      <Wrap>
        <CampaignStartButton campaignId="camp-001" onSuccess={onSuccess} />
      </Wrap>,
    )

    await user.click(screen.getByRole('button', { name: /demarrer/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledTimes(1)
    })
  })
})

describe('CampaignCreateControl', () => {
  it('expose les criteres automobiles de recherche', () => {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as typeof ResizeObserver
    render(<Wrap><CampaignCreateControl /></Wrap>)

    expect(screen.getByLabelText(/marque.*modele/i)).toBeTruthy()
    expect(screen.getByLabelText(/type de vehicule/i)).toBeTruthy()
    expect(screen.getByLabelText(/region ou departement/i)).toBeTruthy()
    expect(screen.getByLabelText(/budget minimum/i)).toBeTruthy()
    expect(screen.getByLabelText(/budget maximum/i)).toBeTruthy()
    expect(screen.getByLabelText(/message/i)).toBeTruthy()
  })
})

describe('AnalyzeListingButton', () => {
  it('declenche l analyse puis appelle onSuccess', async () => {
    const user = userEvent.setup()
    const onSuccess = vi.fn()

    render(
      <Wrap>
        <AnalyzeListingButton listingId="123e4567-e89b-12d3-a456-426614174000" onSuccess={onSuccess} />
      </Wrap>,
    )

    await user.click(screen.getByRole('button', { name: /analyser/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledTimes(1)
    })
  })
})
