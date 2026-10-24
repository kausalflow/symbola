# Symbolon store

A Cloudflare Worker that sells priced packs from the static registry
(distribution design, section 6.1). It is the only server-side code in the
registry. **It is not ready to sell yet**: see "Before the first sale" below.

| Route | Does |
| --- | --- |
| `POST /checkout` (form field `pack`) | Reads the pack's price from the registry's `index.json`, starts a Stripe Checkout that pays the seller's Stripe Connect account minus `PLATFORM_FEE_PERCENT`, and redirects the buyer to it. The pack page's Buy button posts here. |
| `POST /webhook` | Stripe events, checked against `STRIPE_WEBHOOK_SECRET`. `checkout.session.completed` (paid) issues one license per Checkout session, stored with the buyer's Checkout email; `charge.refunded` and `charge.dispute.created` revoke it. This is the only place a license is issued, so a buyer who closes the tab before the success page still has one. |
| `GET /success?session_id=…` | Shows the license the webhook issued and the `symbolon pull … --token …` command, or "reload in a few seconds" if the webhook has not arrived yet. |
| `GET /download/<owner>/<name>` | With `Authorization: Bearer <token>`, streams the pack's latest tarball from R2. `symbolon pull --token` calls this, then checks the sha256 and digest against the public registry as for a free pack. |

A license covers the pack's latest version, the only one the registry serves.
Licenses are kept under the buyer's email (`buyer:<email>:<pack>` in KV), so
support can find a lost one.

## Deploying (not done yet)

Needs a Stripe account with Connect enabled and a Cloudflare account.

1. `npm i -g wrangler && wrangler login`
2. `wrangler kv namespace create LICENSES`, then put its id in `wrangler.toml`.
3. `wrangler r2 bucket create symbolon-packs`
4. `wrangler secret put STRIPE_SECRET_KEY` (use a test-mode key first).
5. In Stripe, add a webhook endpoint `https://<store>/webhook` for `checkout.session.completed`,
   `checkout.session.async_payment_succeeded`, `charge.refunded` and `charge.dispute.created`,
   then `wrangler secret put STRIPE_WEBHOOK_SECRET` with its signing secret.
6. Set `PLATFORM_FEE_PERCENT` in `wrangler.toml`, then `wrangler deploy`.
7. Rebuild the registry with the store: `STORE_URL=https://symbolon-store.<you>.workers.dev registry-site/build.sh …`.
   Priced packs' tarballs land in `registry-site/private/`; upload them with
   `wrangler r2 object put symbolon-packs/packs/<owner>/<name>/latest.tar.gz --file registry-site/private/packs/<owner>/<name>/latest.tar.gz`.
   In CI, set `STORE_URL` and a `CLOUDFLARE_API_TOKEN` secret and add that upload to the docs workflow.

## Before the first sale

- Choose the merchant of record: the platform (destination charges as now, plus Stripe Tax for VAT) or the seller (direct charges).
- Terms of sale and a refund policy on the pack page.
- A way for a buyer to recover a lost license by email (needs an email sender; today support looks it up in KV).
- A check that a seller's Stripe account belongs to the pack's owner, done when recording `seller:<owner>`.

## Sellers

A seller connects a Stripe account once (Stripe Connect Express onboarding,
done from the Stripe dashboard for now), and the platform records it:

```
wrangler kv key put --binding LICENSES seller:<owner> acct_…
```

Then the seller adds a price to the pack manifest and releases:

```toml
[listing]
price = 1900        # minor units: 19.00
currency = "eur"
```

Checkout refuses a pack whose owner has no connected account.

## Tests

`npm test` runs the Worker against stubbed Stripe, KV and R2 (`node --test`; no dependencies).
