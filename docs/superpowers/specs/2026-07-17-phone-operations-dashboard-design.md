# Phone Operations Dashboard Design

## Goal

Provide one authenticated dashboard area where operators can reserve temporary OTP numbers, follow their short lifecycle, inspect received OTP messages, and search/export inbound and outbound campaign SMS without opening provider dashboards.

## Scope

The feature adds a `/phones` control center with two operational views:

- **Temporary numbers:** automatic and manual SMSApp.io reservations, expiry countdown, provider state, account/workflow linkage, received code, and exception actions.
- **SMS history:** a unified timeline backed by `sms_log`, with direction, content, phone, SIM, delivery state, sequence context, search filters, and CSV export.

Temporary OTP numbers remain separate from SMSTools sending SIMs. Reserving a temporary number never makes it eligible for campaign sending.

## Architecture

`PhoneActivation` is the durable local representation of a provider reservation. The provider order ID is unique and is the idempotency boundary. Every acquisition is persisted immediately, with `expires_at`, cost, country, service, origin (`automatic` or `manual`), and optional account/workflow links.

`app.services.phone_operations` owns lifecycle transitions and read models. It calls the existing SMSApp boundary for reserve, poll, and cancel operations. A periodic Celery reconciliation task refreshes active reservations, expires stale rows, and avoids infinite retries. Manual API actions reuse the same service methods.

The API exposes a summary, paginated activation list, reservation/cancel/refresh actions, paginated SMS history, and CSV export. The Next.js page uses a protected same-origin proxy and a single client control center with tabs, filters, refresh, copy actions, and an expiry countdown.

## Data model

`phone_activations` contains:

- provider and unique `provider_order_id`
- `phone_e164`, country, service, cost
- status: `reserved`, `waiting`, `received`, `used`, `cancelled`, `expired`, `refunded`, `failed`
- origin: `automatic` or `manual`
- `expires_at`, `received_at`, `used_at`, timestamps
- optional `platform_account_id` and textual `workflow_id`
- received SMS text/code and last provider error

OTP content is only returned through authenticated endpoints. Provider API tokens remain in Coolify and are never returned to the browser.

## Data flows

### Automatic account creation

1. The existing creation workflow acquires an SMSApp number.
2. The reservation is persisted as `automatic` immediately.
3. Once the account placeholder exists, the activation is linked to the account.
4. OTP reception marks the activation `received`; successful registration marks it `used`.
5. Failures cancel the provider order when possible and persist the final state/error.

### Manual reservation

1. An operator selects country or automatic fallback and service.
2. The backend reserves and persists the number.
3. Celery polls/reconciles until reception, cancellation, or expiry.
4. The dashboard shows live state and allows refresh/cancel for exceptional handling.

### SMS history

The read API queries `SmsLog` for both directions and returns the body, status, SIM, recipient/sender phone, campaign/contact/sequence metadata, cost, and timestamp. CSV export applies the same filters.

## Error handling and safety

- Unique provider order IDs prevent duplicate reservations from being persisted twice.
- Only active reservations may be refreshed or cancelled.
- Expired reservations are marked locally even if the provider is temporarily unavailable.
- Manual acquisition rejects an unconfigured SMSApp connector with a clear `503` response.
- Provider failures are stored as sanitized summaries; API tokens and request headers are never persisted.
- Reconciliation operates on a bounded batch and records failures instead of retrying indefinitely.

## Testing

- Migration/model tests cover fields and uniqueness.
- Service tests cover manual reservation, refresh reception, expiry, cancellation, and account linkage.
- API tests cover protected list/actions, pagination, filters, and CSV.
- Account creation tests prove automatic reservations are persisted and linked.
- Frontend tests cover navigation, rendering, filters, and manual action feedback.
- Full backend/frontend suites and production canaries run before completion.

## Acceptance criteria

- An authenticated operator can reserve a number and immediately see its expiry and state.
- Automatic account creation reservations appear without manual intervention.
- Received OTP content and campaign SMS are available from one page.
- SMS history can be filtered and downloaded as CSV.
- Cancellation, expiry, and provider failures remain visible and auditable.
- Existing account creation and SMS sequence behavior remains passing.
