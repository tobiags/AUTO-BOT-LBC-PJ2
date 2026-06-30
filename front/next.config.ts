import path from 'path'
import type { NextConfig } from 'next'
import { withSentryConfig } from '@sentry/nextjs'

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.resolve(__dirname),
  async rewrites() {
    return [
      {
        source: '/api-backend/:path*',
        destination: `${process.env.API_URL ?? 'http://localhost:8000'}/:path*`,
      },
    ]
  },
}

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: true,
  widenClientFileUpload: true,
  tunnelRoute: '/monitoring',
})
