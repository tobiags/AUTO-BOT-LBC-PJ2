import type { Metadata } from 'next'
import '@radix-ui/themes/styles.css'
import './globals.css'
import { Theme } from '@radix-ui/themes'
import { NavLinks } from '@/components/NavLinks'

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
            <main className="app-main">{children}</main>
          </div>
        </Theme>
      </body>
    </html>
  )
}
