# Symbolon store

A Cloudflare Worker that sells priced packs from the static registry
(distribution design, section 6.1). It is the only server-side code in the
registry, and it does three things:

| Route | Does |
| --- | --- |
| `POST /checkout` (form field `pack`) | Reads the pack's price from the registry's `index.json`, starts a Stripe Checkout that pays the seller's Stripe Connect account minus `PLATFORM_FEE_PERCENT`, and redirects the buyer to it. The pack page's Buy button posts here. |
| `GET /success?session_id=…` | After payment, issues one license token per Checkout session and shows the `symbolon pull … --token …` command. Reloading shows the same token. |
| `GET /download/<owner>/<name>` | With `Authorization: Bearer <token>`, streams the pack's latest tarball from R2. `symbolon pull --token` calls this, then checks the sha256 and digest against the public registry as for a free pack. |

A license covers the pack's latest version, the only one the registry serves.

## Deploying (not done yet)

Needs a Stripe account with Connect enabled and a Cloudflare account.

1. `npm i -g wrangler && wrangler login`
2. `wrangler kv namespace create LICENSES`, then put its id in `wrangler.toml`.
3. `wrangler r2 bucket create symbolon-packs`
4. `wrangler secret put STRIPE_SECRET_KEY` (use a test-mode key first).
5. Set `PLATFORM_FEE_PERCENT` in `wrangler.toml`, then `wrangler deploy`.
6. Rebuild the registry with the store: `STORE_URL=https://symbolon-store.<you>.workers.dev registry-site/build.sh …`.
   Priced packs' tarballs land in `registry-site/private/`; upload them with
   `wrangler r2 object put symbolon-packs/packs/<owner>/<name>/latest.tar.gz --file registry-site/private/packs/<owner>/<name>/latest.tar.gz`.
   In CI, set `STORE_URL` and a `CLOUDFLARE_API_TOKEN` secret and add that upload to the docs workflow.

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
