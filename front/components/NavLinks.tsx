'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import {
  Activity,
  BarChart3,
  Bot,
  Boxes,
  BriefcaseBusiness,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  Menu,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings2,
  ShieldCheck,
  Users,
  Workflow,
  X,
} from 'lucide-react'
import { LogoutButton } from './LogoutButton'
import { OperatorStatus } from './OperatorStatus'

type NavItem = { href: string; label: string; compact: string; icon: typeof LayoutDashboard }

const NAV_GROUPS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: 'Pilotage',
    items: [
      { href: '/dashboard', label: 'Tableau de bord', compact: 'Dashboard', icon: LayoutDashboard },
      { href: '/workflows', label: 'Workflows', compact: 'Workflows', icon: Workflow },
      { href: '/listings', label: 'Annonces', compact: 'Annonces', icon: ClipboardList },
      { href: '/campaigns', label: 'Campagnes', compact: 'Campagnes', icon: BriefcaseBusiness },
      { href: '/messaging', label: 'Messagerie LBC', compact: 'Messages', icon: MessageSquare },
    ],
  },
  {
    label: 'Ressources',
    items: [
      { href: '/sectors', label: 'Secteurs', compact: 'Secteurs', icon: Gauge },
      { href: '/accounts', label: 'Comptes LBC', compact: 'Comptes', icon: Boxes },
      { href: '/users', label: 'Utilisateurs', compact: 'Utilisateurs', icon: Users },
      { href: '/analyzer', label: 'Analyste prix', compact: 'Analyse', icon: BarChart3 },
    ],
  },
  {
    label: 'Système',
    items: [
      { href: '/connectors', label: 'Connecteurs', compact: 'Connecteurs', icon: Activity },
      { href: '/settings', label: 'Administration', compact: 'Admin', icon: Settings2 },
      { href: '/audit', label: 'Audit', compact: 'Audit', icon: ShieldCheck },
      { href: '/browser-use', label: 'Browser Use', compact: 'Browser Use', icon: Bot },
      { href: '/lab', label: 'Laboratoire', compact: 'Lab', icon: Search },
    ],
  },
]

function NavItem({ item, collapsed, onNavigate }: { item: NavItem; collapsed?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname()
  const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
  const Icon = item.icon

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={`dashboard-nav-item${active ? ' is-active' : ''}`}
      aria-current={active ? 'page' : undefined}
      title={collapsed ? item.label : undefined}
    >
      <Icon size={17} strokeWidth={active ? 2.4 : 1.9} aria-hidden="true" />
      <span className="dashboard-nav-label">{collapsed ? item.compact : item.label}</span>
    </Link>
  )
}

export function NavLinks() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  if (pathname === '/login') return null

  return (
    <>
      <button className="mobile-nav-toggle" type="button" onClick={() => setMobileOpen((value) => !value)} aria-label="Ouvrir la navigation">
        {mobileOpen ? <X size={19} /> : <Menu size={19} />}
      </button>
      <aside className={`desktop-nav${collapsed ? ' is-collapsed' : ''}${mobileOpen ? ' is-mobile-open' : ''}`} aria-label="Navigation principale">
        <div className="dashboard-brand">
          <div className="dashboard-brand-mark">A</div>
          <div className="dashboard-brand-copy">
            <strong>AutoTransfert</strong>
            <span>Control tower</span>
          </div>
          <button className="dashboard-collapse-button" type="button" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? 'Développer le menu' : 'Réduire le menu'}>
            {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>
        <div className="dashboard-nav-scroll">
          {NAV_GROUPS.map((group) => (
            <section className="dashboard-nav-group" key={group.label}>
              <div className="dashboard-nav-group-label">{group.label}</div>
              {group.items.map((item) => <NavItem key={item.href} item={item} collapsed={collapsed} onNavigate={() => setMobileOpen(false)} />)}
            </section>
          ))}
        </div>
        <div className="dashboard-sidebar-footer">
          <OperatorStatus />
          <LogoutButton />
        </div>
      </aside>
      <nav className="mobile-nav" aria-label="Navigation mobile">
        {NAV_GROUPS.flatMap((group) => group.items).map((item) => <NavItem key={item.href} item={item} onNavigate={() => setMobileOpen(false)} />)}
      </nav>
    </>
  )
}
