'use client'

import { Button, Card, Flex, Heading, Select, Table, Text, TextField } from '@radix-ui/themes'
import { FormEvent, useEffect, useState } from 'react'

type User = {
  id: string
  email: string
  display_name: string
  role: 'administrateur' | 'manager' | 'operateur'
  active: boolean
  created_at: string
  temporary_password?: string
}

const ROLE_LABELS = {
  administrateur: 'Administrateur',
  manager: 'Manager',
  operateur: 'Opérateur',
}

export function WorkspaceUsersControl({ canCreate }: { canCreate: boolean }) {
  const [users, setUsers] = useState<User[]>([])
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<User['role']>('operateur')
  const [feedback, setFeedback] = useState('')
  const [temporaryPassword, setTemporaryPassword] = useState('')

  async function loadUsers() {
    const response = await fetch('/api/workspace/users', { cache: 'no-store' })
    if (response.ok) setUsers(await response.json())
  }

  useEffect(() => { void loadUsers() }, [])

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFeedback('')
    setTemporaryPassword('')
    const response = await fetch('/api/workspace/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, display_name: displayName, role }),
    })
    const body = await response.json()
    if (!response.ok) {
      setFeedback(body.detail?.code === 'USER_ALREADY_EXISTS' ? 'Cet e-mail existe déjà.' : body.error ?? 'Création impossible.')
      return
    }
    setTemporaryPassword(body.temporary_password)
    setFeedback('Utilisateur créé. Transmets ce mot de passe temporaire une seule fois.')
    setEmail('')
    setDisplayName('')
    setRole('operateur')
    await loadUsers()
  }

  return (
    <Flex direction="column" gap="5">
      <Heading size="6">Utilisateurs du workspace</Heading>
      <Text size="2" color="gray">Workspace AutoTransfert partagé. Les annonces et campagnes sont visibles par l’équipe, avec des droits selon le rôle.</Text>
      {canCreate && (
        <Card>
          <form onSubmit={createUser}>
            <Flex direction="column" gap="3">
              <Heading size="4">Créer un utilisateur</Heading>
              <TextField.Root placeholder="Nom affiché" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
              <TextField.Root type="email" placeholder="E-mail de connexion" value={email} onChange={(e) => setEmail(e.target.value)} required />
              <Select.Root value={role} onValueChange={(value) => setRole(value as User['role'])}>
                <Select.Trigger placeholder="Rôle" />
                <Select.Content>
                  <Select.Item value="operateur">Opérateur</Select.Item>
                  <Select.Item value="manager">Manager</Select.Item>
                  <Select.Item value="administrateur">Administrateur</Select.Item>
                </Select.Content>
              </Select.Root>
              <Button type="submit">Créer le compte</Button>
              {feedback && <Text size="2" role="status">{feedback}</Text>}
              {temporaryPassword && <Text size="2" weight="bold">Mot de passe temporaire : {temporaryPassword}</Text>}
            </Flex>
          </form>
        </Card>
      )}
      <Table.Root variant="surface">
        <Table.Header><Table.Row><Table.ColumnHeaderCell>Nom</Table.ColumnHeaderCell><Table.ColumnHeaderCell>E-mail</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Rôle</Table.ColumnHeaderCell><Table.ColumnHeaderCell>Statut</Table.ColumnHeaderCell></Table.Row></Table.Header>
        <Table.Body>
          {users.map((user) => <Table.Row key={user.id}><Table.Cell>{user.display_name}</Table.Cell><Table.Cell>{user.email}</Table.Cell><Table.Cell>{ROLE_LABELS[user.role]}</Table.Cell><Table.Cell>{user.active ? 'Actif' : 'Désactivé'}</Table.Cell></Table.Row>)}
          {users.length === 0 && <Table.Row><Table.Cell colSpan={4}><Text color="gray">Aucun utilisateur trouvé.</Text></Table.Cell></Table.Row>}
        </Table.Body>
      </Table.Root>
    </Flex>
  )
}
