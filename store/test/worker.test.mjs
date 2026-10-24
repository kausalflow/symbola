// Run with: node --test store/test
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import worker, { verifyStripeSignature } from "../src/worker.js";

const INDEX = {
  packs: [
    { id: "acme/desk", price: { amount: 1900, currency: "eur" } },
    { id: "acme/free", price: null },
  ],
};

let kv, r2, stripeCalls, sessions;

function kvStore() {
  const m = new Map();
  return {
    m,
    async get(k, type) { const v = m.get(k) ?? null; return v && type === "json" ? JSON.parse(v) : v; },
    async put(k, v) { m.set(k, v); },
  };
}

beforeEach(() => {
  kv = kvStore();
  kv.m.set("seller:acme", "acct_123");
  r2 = { async get(k) { return k === "packs/acme/desk/latest.tar.gz" ? { body: "TARBALL" } : null; } };
  stripeCalls = [];
  sessions = { cs_paid: { payment_status: "paid", metadata: { pack: "acme/desk" } },
               cs_open: { payment_status: "unpaid", metadata: { pack: "acme/desk" } } };
  globalThis.fetch = async (url, init = {}) => {
    url = String(url);
    if (url === "https://registry.test/index.json") return Response.json(INDEX);
    if (url.startsWith("https://api.stripe.com/v1/checkout/sessions")) {
      stripeCalls.push({ url, init });
      if (init.method === "POST") return Response.json({ id: "cs_new", url: "https://checkout.stripe.test/cs_new" });
      const s = sessions[url.split("/").pop()];
      return s ? Response.json(s) : Response.json({ error: { message: "no such session" } }, { status: 404 });
    }
    throw new Error(`unexpected fetch ${url}`);
  };
});

const env = () => ({ LICENSES: kv, PACKS: r2, REGISTRY_URL: "https://registry.test", PLATFORM_FEE_PERCENT: "15",
                     STRIPE_SECRET_KEY: "sk_test", STRIPE_WEBHOOK_SECRET: "whsec_test" });
const call = (path, init) => worker.fetch(new Request(`https://store.test${path}`, init), env());
const form = (pack) => ({ method: "POST", body: new URLSearchParams({ pack }) });

test("checkout pays the seller minus the platform fee", async () => {
  const res = await call("/checkout", form("acme/desk"));
  assert.equal(res.status, 303);
  assert.equal(res.headers.get("location"), "https://checkout.stripe.test/cs_new");
  const sent = new URLSearchParams(stripeCalls[0].init.body);
  assert.equal(sent.get("line_items[0][price_data][unit_amount]"), "1900");
  assert.equal(sent.get("payment_intent_data[application_fee_amount]"), "285");
  assert.equal(sent.get("payment_intent_data[transfer_data][destination]"), "acct_123");
  assert.equal(sent.get("metadata[pack]"), "acme/desk");
});

test("checkout refuses free, unknown and unconnected packs", async () => {
  assert.equal((await call("/checkout", form("acme/free"))).status, 409);
  assert.equal((await call("/checkout", form("acme/none"))).status, 404);
  assert.equal((await call("/checkout", form("../etc"))).status, 400);
  kv.m.delete("seller:acme");
  assert.equal((await call("/checkout", form("acme/desk"))).status, 409);
});

async function signed(event, secret = "whsec_test", t = Math.floor(Date.now() / 1000)) {
  const body = JSON.stringify(event);
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${t}.${body}`));
  const v1 = [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return { method: "POST", body, headers: { "stripe-signature": `t=${t},v1=${v1}` } };
}

const paid = (id = "cs_paid", status = "paid") => ({
  type: "checkout.session.completed",
  data: { object: { id, payment_status: status, payment_intent: "pi_1", metadata: { pack: "acme/desk" },
                    customer_details: { email: "Buyer@Example.com" } } },
});

async function licenseFor(session) {
  const page = await (await call(`/success?session_id=${session}`)).text();
  return page.match(/--token (sym_[0-9a-f]+)/)?.[1];
}

test("only the webhook issues a license, once, tied to the buyer's email", async () => {
  assert.equal(await licenseFor("cs_paid"), undefined, "the success page alone issues nothing");
  assert.equal((await call("/webhook", await signed(paid()))).status, 200);
  assert.equal((await call("/webhook", await signed(paid()))).status, 200, "Stripe retries are harmless");
  const token = await licenseFor("cs_paid");
  assert.ok(token);
  assert.equal(await licenseFor("cs_paid"), token, "reloading the success page shows the same license");
  assert.equal([...kv.m.keys()].filter((k) => k.startsWith("license:")).length, 1);
  assert.equal(await kv.get("buyer:buyer@example.com:acme/desk"), token);
  assert.equal(stripeCalls.length, 0, "no Stripe API call is needed after checkout");
});

test("the webhook refuses bad or stale signatures and unpaid sessions", async () => {
  assert.equal((await call("/webhook", await signed(paid(), "whsec_wrong"))).status, 400);
  const old = Math.floor(Date.now() / 1000) - 3600;
  assert.equal((await call("/webhook", await signed(paid(), "whsec_test", old))).status, 400);
  assert.equal((await call("/webhook", { method: "POST", body: JSON.stringify(paid()) })).status, 400);
  await call("/webhook", await signed(paid("cs_open", "unpaid")));
  assert.equal([...kv.m.keys()].filter((k) => k.startsWith("license:")).length, 0);
  assert.equal(await verifyStripeSignature("{}", "t=1,v1=00", "whsec_test", 1), false);
});

test("a license downloads only its pack, and a refund revokes it", async () => {
  await call("/webhook", await signed(paid()));
  const token = await licenseFor("cs_paid");
  const auth = (t) => ({ headers: { authorization: `Bearer ${t}` } });
  const ok = await call("/download/acme/desk", auth(token));
  assert.equal(ok.status, 200);
  assert.equal(await ok.text(), "TARBALL");
  assert.equal((await call("/download/acme/free", auth(token))).status, 403);
  assert.equal((await call("/download/acme/desk", auth("sym_wrong"))).status, 403);
  assert.equal((await call("/download/acme/desk")).status, 403);

  await call("/webhook", await signed({ type: "charge.refunded", data: { object: { payment_intent: "pi_1" } } }));
  const gone = await call("/download/acme/desk", auth(token));
  assert.equal(gone.status, 403);
  assert.match(await gone.text(), /revoked/);
});
