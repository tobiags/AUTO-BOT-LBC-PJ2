'use client'

import { FormEvent, Suspense, useState } from 'react'
import { Box, Button, Heading, Text, TextField } from '@radix-ui/themes'
import { LogIn } from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'

function LoginForm() {
  const router = useRouter()
  const search = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)
    const form = new FormData(event.currentTarget)
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: form.get('username'),
        password: form.get('password'),
      }),
    })
    setPending(false)
    if (!response.ok) {
      setError('Connexion impossible')
      return
    }
    const next = search.get('next')
    router.replace(next?.startsWith('/') ? next : '/dashboard')
  }

  return (
    <Box style={{ width: 'min(100%, 360px)', margin: '12vh auto' }}>
      <Heading size="6" mb="2">AutoTransfert</Heading>
      <Text size="2" color="gray" as="div" mb="5">Acces au centre de controle</Text>
      <form onSubmit={submit}>
        <Text size="2" weight="bold" as="div" mb="1">Operateur</Text>
        <TextField.Root name="username" autoComplete="username" required mb="3" />
        <Text size="2" weight="bold" as="div" mb="1">Mot de passe</Text>
        <TextField.Root
          name="password" type="password" autoComplete="current-password" required mb="3"
        />
        {error && <Text color="red" size="2" as="div" mb="3">{error}</Text>}
        <Button disabled={pending} style={{ width: '100%' }}>
          <LogIn size={15} /> Se connecter
        </Button>
      </form>
    </Box>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Box style={{ margin: '12vh auto', width: 360 }}>Chargement...</Box>}>
      <LoginForm />
    </Suspense>
  )
}
