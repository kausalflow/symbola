// Run with: node --test store/test
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import worker from "../src/worker.js";

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
                     STRIPE_SECRET_KEY: "sk_test" });
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

test("a paid session gets one license, and it downloads only its pack", async () => {
  const page = await (await call("/success?session_id=cs_paid")).text();
  const token = page.match(/--token (sym_[0-9a-f]+)/)[1];
  const again = await (await call("/success?session_id=cs_paid")).text();
  assert.ok(again.includes(token), "reloading the success page shows the same license");

  const ok = await call("/download/acme/desk", { headers: { authorization: `Bearer ${token}` } });
  assert.equal(ok.status, 200);
  assert.equal(await ok.text(), "TARBALL");
  assert.equal((await call("/download/acme/free", { headers: { authorization: `Bearer ${token}` } })).status, 403);
  assert.equal((await call("/download/acme/desk", { headers: { authorization: "Bearer sym_wrong" } })).status, 403);
  assert.equal((await call("/download/acme/desk")).status, 403);
});

test("an unpaid session gets no license", async () => {
  assert.equal((await call("/success?session_id=cs_open")).status, 402);
  assert.equal([...kv.m.keys()].filter((k) => k.startsWith("license:")).length, 0);
});
