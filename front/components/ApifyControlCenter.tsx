'use client'

import { Box, Flex, Grid, Heading, Text } from '@radix-ui/themes'

import type { ApifyDashboard } from '@/lib/apify-api'
import { ApifyAccountsPanel } from './ApifyAccountsPanel'
import { ApifyBindingsPanel } from './ApifyBindingsPanel'

export function ApifyControlCenter({ initialData }: { initialData: ApifyDashboard }) {
  const metrics = [
    ['Comptes actifs', initialData.summary.accounts_active],
    ['Actors actifs', initialData.summary.bindings_enabled],
    ['Leads importes', initialData.summary.items_imported],
    ['Exceptions', initialData.summary.exceptions_open],
  ] as const

  return (
    <Box>
      <Flex role="tablist" aria-label="Sections Apify" gap="2" mb="4">
        <button role="tab" aria-selected="true" type="button">Vue d&apos;ensemble</button>
        <button role="tab" aria-selected="false" type="button">Comptes et Actors</button>
      </Flex>
      <Grid columns={{ initial: '2', md: '4' }} gap="3" mb="5">
        {metrics.map(([label, value]) => (
          <Box key={label} p="3" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
            <Text size="1" color="gray" as="div">{label}</Text>
            <Heading size="5">{value}</Heading>
          </Box>
        ))}
      </Grid>
      <Grid columns={{ initial: '1', lg: '2' }} gap="4">
        <ApifyAccountsPanel initialAccounts={initialData.accounts} />
        <ApifyBindingsPanel initialBindings={initialData.bindings} />
      </Grid>
    </Box>
  )
}
