'use client'

import { useEffect, useState } from 'react'
import { Badge, Box, Button, Flex, Heading, Text } from '@radix-ui/themes'

import type { ApifyLearning } from '@/lib/apify-api'

export function ApifyLearningPanel({ initialLearning }: { initialLearning: ApifyLearning }) {
  const [learning, setLearning] = useState(initialLearning)
  const [isAdmin, setIsAdmin] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  useEffect(() => {
    fetch('/api/auth/session')
      .then((response) => response.ok ? response.json() : null)
      .then((session) => setIsAdmin(session?.role === 'admin'))
      .catch(() => setIsAdmin(false))
  }, [])

  async function rollback(profileId: string) {
    setMessage(null)
    const response = await fetch(`/api/apify/profiles/${profileId}/rollback`, { method: 'POST' })
    if (!response.ok) {
      setMessage('Rollback impossible')
      return
    }
    const active = await response.json()
    setLearning((current) => ({
      ...current,
      profiles: current.profiles.map((profile) => profile.id === active.id ? active : profile),
    }))
    setMessage('Profil restaure')
  }

  return (
    <Box>
      <Heading size="4" mb="3">Apprentissage controle</Heading>
      {message && <Text role="status" as="div" mb="3">{message}</Text>}
      <Heading size="3" mb="2">Profils</Heading>
      <Flex direction="column" gap="2" mb="4">
        {learning.profiles.map((profile) => (
          <Box key={profile.id} p="3" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
            <Flex justify="between" gap="3">
              <Text>Version {profile.version} · schema {profile.schema_fingerprint}</Text>
              <Badge>{profile.status}</Badge>
            </Flex>
            <pre>{JSON.stringify(profile.metrics, null, 2)}</pre>
            {isAdmin && profile.status === 'retired' && <Button size="1" onClick={() => rollback(profile.id)}>Restaurer profil {profile.version}</Button>}
          </Box>
        ))}
      </Flex>
      <Heading size="3" mb="2">Experiences fantomes</Heading>
      <Flex direction="column" gap="2" mb="4">
        {learning.experiments.map((experiment) => (
          <Box key={experiment.id} p="3" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
            <Flex justify="between"><Text>Corpus {experiment.corpus_size}</Text><Badge>{experiment.decision ?? 'crash'}</Badge></Flex>
            <Text size="1" color="gray" as="div">{experiment.reason ?? 'sans regression'}</Text>
            <Text size="1" weight="bold" as="div">Baseline</Text><pre>{JSON.stringify(experiment.baseline_metrics, null, 2)}</pre>
            <Text size="1" weight="bold" as="div">Candidat</Text><pre>{JSON.stringify(experiment.candidate_metrics, null, 2)}</pre>
          </Box>
        ))}
      </Flex>
      <Heading size="3" mb="2">Exceptions et coupe-circuits</Heading>
      <Flex direction="column" gap="2">
        {learning.exceptions.map((exception) => (
          <Box key={exception.id} p="3" style={{ border: '1px solid var(--red-5)', borderRadius: 8 }}>
            <Text weight="bold" as="div">{exception.category}</Text>
            <pre>{JSON.stringify(exception.evidence, null, 2)}</pre>
          </Box>
        ))}
      </Flex>
    </Box>
  )
}
