import type { Metadata } from 'next'
import '@radix-ui/themes/styles.css'
import './globals.css'
import { Theme } from '@radix-ui/themes'
import { NavLinks } from '@/components/NavLinks'
import { Activity, Bell, Search } from 'lucide-react'

export const metadata: Metadata = {
  title: 'AutoTransfert — Back-office',
  description: 'Gestion campagnes LBC & analyste prix',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body style={{ margin: 0 }}>
        <Theme accentColor="blue" grayColor="slate" radius="medium" scaling="100%">
          <div className="app-shell">
            <NavLinks />
            <main className="app-main">
              <header className="dashboard-topbar">
                <div className="dashboard-topbar-context">
                  <span className="dashboard-topbar-kicker">Workspace</span>
                  <strong>AutoTransfert</strong>
                </div>
                <div className="dashboard-topbar-actions">
                  <span className="dashboard-live-status"><Activity size={14} /> Services opérationnels</span>
                  <button type="button" className="dashboard-icon-button" aria-label="Rechercher"><Search size={16} /></button>
                  <button type="button" className="dashboard-icon-button" aria-label="Notifications"><Bell size={16} /></button>
                </div>
              </header>
              {children}
            </main>
          </div>
        </Theme>
      </body>
    </html>
  )
}
