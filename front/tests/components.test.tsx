import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Theme } from '@radix-ui/themes'
import { AnalyzeListingButton } from '@/components/AnalyzeListingButton'
import { CampaignStartButton } from '@/components/CampaignStartButton'
import { CampaignCreateControl } from '@/components/CampaignCreateControl'
import { AccountIdentifier } from '@/components/AccountIdentifier'
import { AccountControls } from '@/components/AccountControls'
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
  it('expose les criteres de recherche et le canal multi-disponibilite', () => {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as typeof ResizeObserver
    render(<Wrap><CampaignCreateControl /></Wrap>)

    expect(screen.getByLabelText(/région/i)).toBeTruthy()
    expect(screen.getByLabelText(/département/i)).toBeTruthy()
    expect(screen.getByLabelText(/budget minimum/i)).toBeTruthy()
    expect(screen.getByLabelText(/budget maximum/i)).toBeTruthy()
    expect(screen.getByLabelText(/année maximale/i)).toBeTruthy()
    expect(screen.getByLabelText(/kilométrage maximal/i)).toBeTruthy()
    expect(screen.getByLabelText(/canal de campagne/i)).toBeTruthy()
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

describe('AccountIdentifier', () => {
  it('affiche et copie un identifiant cree', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    render(
      <Wrap>
        <AccountIdentifier label="E-mail" value="contact.test@mail.ecovente.com" />
      </Wrap>,
    )

    expect(screen.getByText('contact.test@mail.ecovente.com')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /copier e-mail/i }))
    expect(writeText).toHaveBeenCalledWith('contact.test@mail.ecovente.com')
  })

  it('indique lorsqu aucun numero OTP n est encore attribue', () => {
    render(
      <Wrap>
        <AccountIdentifier label="Numero OTP" value={null} />
      </Wrap>,
    )

    expect(screen.getByText(/non attribue/i)).toBeTruthy()
  })
})

describe('AccountControls', () => {
  it('explique quand une action est refusee car elle requiert un administrateur', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: { code: 'ADMIN_REQUIRED' } }),
    }))
    vi.stubGlobal('confirm', vi.fn().mockReturnValue(true))

    render(
      <Wrap>
        <AccountControls accountId="acc-001" status="ACTIF" hasProfile={false} />
      </Wrap>,
    )

    await user.click(screen.getByRole('button', { name: /quarantaine/i }))

    expect(await screen.findByText(/reservee a l administrateur/i)).toBeTruthy()
  })

  it('confirme visiblement une commande terminee', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'completed' }),
    }))
    vi.stubGlobal('confirm', vi.fn().mockReturnValue(true))

    render(
      <Wrap>
        <AccountControls accountId="acc-001" status="ACTIF" hasProfile={false} />
      </Wrap>,
    )

    await user.click(screen.getByRole('button', { name: /quarantaine/i }))

    expect(await screen.findByText(/quarantaine terminee/i)).toBeTruthy()
  })
})
