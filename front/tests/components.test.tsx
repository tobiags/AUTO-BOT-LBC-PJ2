import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Theme } from '@radix-ui/themes'
import { PriceScoreBadge } from '@/components/PriceScoreBadge'

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
