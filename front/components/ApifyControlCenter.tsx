'use client'

import { useState } from 'react'
import { Box, Flex, Grid, Heading, Text } from '@radix-ui/themes'

import type { ApifyDashboard } from '@/lib/apify-api'
import { ApifyAccountsPanel } from './ApifyAccountsPanel'
import { ApifyBindingsPanel } from './ApifyBindingsPanel'
import { ApifyLearningPanel } from './ApifyLearningPanel'
import { ApifyResultsPanel } from './ApifyResultsPanel'
import { ApifyRunsPanel } from './ApifyRunsPanel'

type Tab = 'overview' | 'accounts' | 'runs' | 'results' | 'learning'

export function ApifyControlCenter({ initialData }: { initialData: ApifyDashboard }) {
  const [tab, setTab] = useState<Tab>('overview')
  const metrics = [
    ['Comptes actifs', initialData.summary.accounts_active],
    ['Actors actifs', initialData.summary.bindings_enabled],
    ['Leads importes', initialData.summary.items_imported],
    ['Exceptions', initialData.summary.exceptions_open],
  ] as const

  return (
    <Box>
      <Flex role="tablist" aria-label="Sections Apify" gap="2" mb="4">
        {([
          ['overview', "Vue d'ensemble"],
          ['accounts', 'Comptes et Actors'],
          ['runs', 'Runs'],
          ['results', 'Resultats'],
          ['learning', 'Apprentissage'],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            aria-controls={`apify-panel-${value}`}
            type="button"
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </Flex>
      {(tab === 'overview' || tab === 'accounts') && (
        <Box role="tabpanel" id={`apify-panel-${tab}`}>
          {tab === 'overview' && (
            <Grid columns={{ initial: '2', md: '4' }} gap="3" mb="5">
              {metrics.map(([label, value]) => (
                <Box key={label} p="3" style={{ border: '1px solid var(--gray-5)', borderRadius: 8 }}>
                  <Text size="1" color="gray" as="div">{label}</Text>
                  <Heading size="5">{value}</Heading>
                </Box>
              ))}
            </Grid>
          )}
          <Grid columns={{ initial: '1', lg: '2' }} gap="4">
            <ApifyAccountsPanel initialAccounts={initialData.accounts} />
            <ApifyBindingsPanel initialBindings={initialData.bindings} />
          </Grid>
        </Box>
      )}
      {tab === 'runs' && <Box role="tabpanel" id="apify-panel-runs"><ApifyRunsPanel runs={initialData.runs.items} /></Box>}
      {tab === 'results' && <Box role="tabpanel" id="apify-panel-results"><ApifyResultsPanel items={initialData.items.items} runs={initialData.runs.items} bindings={initialData.bindings} /></Box>}
      {tab === 'learning' && <Box role="tabpanel" id="apify-panel-learning"><ApifyLearningPanel initialLearning={initialData.learning} /></Box>}
    </Box>
  )
}
