'use client'

import { Button } from '@radix-ui/themes'
import { LogOut } from 'lucide-react'
import { useRouter } from 'next/navigation'

export function LogoutButton() {
  const router = useRouter()
  return (
    <Button
      variant="ghost"
      size="1"
      onClick={async () => {
        await fetch('/api/auth/logout', { method: 'POST' })
        router.replace('/login')
      }}
    >
      <LogOut size={14} /> Deconnexion
    </Button>
  )
}
