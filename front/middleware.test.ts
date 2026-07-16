import { describe, expect, it } from 'vitest'

import { config } from './middleware'

describe('middleware route protection', () => {
  it('protects the Apify dashboard and proxy routes', () => {
    expect(config.matcher).toContain('/apify/:path*')
    expect(config.matcher).toContain('/api/apify/:path*')
  })
})
