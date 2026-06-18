import { Badge } from '@radix-ui/themes'

type Props = { score: number | null }

export function PriceScoreBadge({ score }: Props) {
  if (score === null) return <Badge color="gray">—</Badge>
  if (score >= 8) return <Badge color="green">{score}/10</Badge>
  if (score >= 6) return <Badge color="orange">{score}/10</Badge>
  return <Badge color="red">{score}/10</Badge>
}
