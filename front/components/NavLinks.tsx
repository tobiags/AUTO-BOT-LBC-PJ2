'use client'

import { Flex, Text } from '@radix-ui/themes'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LogoutButton } from './LogoutButton'
import { OperatorStatus } from './OperatorStatus'

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Tableau de bord', compact: 'Dashboard' },
  { href: '/workflows', label: 'Workflows', compact: 'Workflows' },
  { href: '/listings', label: 'Annonces', compact: 'Annonces' },
  { href: '/campaigns', label: 'Campagnes', compact: 'Campagnes' },
  { href: '/sectors', label: 'Secteurs', compact: 'Secteurs' },
  { href: '/messaging', label: 'Messagerie LBC', compact: 'Messages' },
  { href: '/accounts', label: 'Comptes LBC', compact: 'Comptes' },
  { href: '/users', label: 'Utilisateurs', compact: 'Utilisateurs' },
  { href: '/analyzer', label: 'Analyste prix', compact: 'Analyse' },
  { href: '/connectors', label: 'Connecteurs', compact: 'Connecteurs' },
  { href: '/settings', label: 'Administration', compact: 'Admin' },
  { href: '/audit', label: 'Audit', compact: 'Audit' },
  { href: '/browser-use', label: 'Browser Use', compact: 'Browser Use' },
  { href: '/lab', label: 'Laboratoire', compact: 'Lab' },
]

function NavItem({ href, label }: { href: string; label: string }) {
  const pathname = usePathname()
  const active = pathname === href

  return (
    <Link
      href={href}
      style={{
        display: 'block',
        flexShrink: 0,
        padding: '8px 10px',
        borderRadius: 6,
        textDecoration: 'none',
        whiteSpace: 'nowrap',
        backgroundColor: active ? 'var(--blue-3)' : 'transparent',
        color: active ? 'var(--blue-11)' : 'var(--gray-11)',
        fontSize: 14,
        fontWeight: active ? 600 : 400,
      }}
    >
      {label}
    </Link>
  )
}

export function NavLinks() {
  const pathname = usePathname()
  if (pathname === '/login') return null
  return (
    <>
      <nav className="desktop-nav" aria-label="Navigation principale">
        <Text size="4" weight="bold" as="div" mb="6" color="blue">
          AutoTransfert
        </Text>
        <Flex direction="column" gap="1">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.href} href={item.href} label={item.label} />
          ))}
        </Flex>
        <OperatorStatus />
        <LogoutButton />
      </nav>
      <nav className="mobile-nav" aria-label="Navigation mobile">
        {NAV_ITEMS.map((item) => {
          return <NavItem key={item.href} href={item.href} label={item.compact} />
        })}
      </nav>
    </>
  )
}
