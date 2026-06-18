'use client'
import { Box, Flex, Text } from '@radix-ui/themes'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Tableau de bord' },
  { href: '/listings', label: 'Annonces' },
  { href: '/campaigns', label: 'Campagnes' },
  { href: '/accounts', label: 'Comptes LBC' },
  { href: '/analyzer', label: 'Analyste prix' },
]

export function NavLinks() {
  const pathname = usePathname()

  return (
    <Box
      style={{
        width: 220,
        borderRight: '1px solid var(--gray-4)',
        padding: '24px 16px',
        minHeight: '100vh',
        flexShrink: 0,
      }}
    >
      <Text size="4" weight="bold" as="div" mb="6" color="blue">
        AutoTransfert
      </Text>
      <Flex direction="column" gap="1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                textDecoration: 'none',
                padding: '8px 12px',
                borderRadius: 6,
                backgroundColor: active ? 'var(--blue-3)' : 'transparent',
                color: active ? 'var(--blue-11)' : 'var(--gray-11)',
                fontWeight: active ? 600 : 400,
                fontSize: 14,
                display: 'block',
              }}
            >
              {item.label}
            </Link>
          )
        })}
      </Flex>
    </Box>
  )
}
