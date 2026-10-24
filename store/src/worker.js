// The Symbolon store: sells priced packs from the static registry.
//
//   POST /checkout              form or JSON {pack}: start a Stripe Checkout for that pack
//   GET  /success?session_id=   after payment: issue the buyer's license token
//   GET  /download/<owner>/<name>   with "Authorization: Bearer <token>": the pack's latest tarball
//
// Prices come from the registry's public index.json, so the site and the store
// never disagree. Payment goes to the seller's Stripe Connect account, minus the
// platform fee. Licenses cover the pack's latest version, the only one served.
//
// Bindings (wrangler.toml): LICENSES (KV), PACKS (R2), REGISTRY_URL,
// PLATFORM_FEE_PERCENT; secret STRIPE_SECRET_KEY.
// KV keys: seller:<owner> -> Stripe account id; license:<token> -> {pack, session};
// session:<checkout session id> -> token.

const STRIPE = "https://api.stripe.com/v1";
const PACK_RE = /^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9-]*$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (request.method === "POST" && url.pathname === "/checkout") return await checkout(request, env, url);
      if (request.method === "GET" && url.pathname === "/success") return await success(env, url);
      if (request.method === "GET" && url.pathname.startsWith("/download/")) return await download(request, env, url);
      return text("not found", 404);
    } catch (e) {
      return text(`store error: ${e.message}`, 502);
    }
  },
};

function text(body, status = 200) {
  return new Response(body, { status, headers: { "content-type": "text/plain; charset=utf-8" } });
}

function escape(s) {
  return String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

async function stripe(env, method, path, form) {
  const res = await fetch(`${STRIPE}${path}`, {
    method,
    headers: {
      authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
      ...(form ? { "content-type": "application/x-www-form-urlencoded" } : {}),
    },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message ?? `stripe ${res.status}`);
  return data;
}

async function listing(env, pack) {
  const res = await fetch(`${env.REGISTRY_URL.replace(/\/$/, "")}/index.json`);
  if (!res.ok) throw new Error(`registry index ${res.status}`);
  return (await res.json()).packs.find((p) => p.id === pack);
}

async function checkout(request, env, url) {
  const type = request.headers.get("content-type") ?? "";
  const body = type.includes("application/json")
    ? await request.json()
    : Object.fromEntries(await request.formData());
  const pack = String(body.pack ?? "");
  if (!PACK_RE.test(pack)) return text("pack must look like owner/name", 400);
  const entry = await listing(env, pack);
  if (!entry) return text(`${pack} is not in the registry`, 404);
  if (!entry.price) return text(`${pack} is free; pull it directly`, 409);
  const seller = await env.LICENSES.get(`seller:${pack.split("/")[0]}`);
  if (!seller) return text(`the publisher of ${pack} has not connected a payout account yet`, 409);

  const { amount, currency } = entry.price;
  const fee = Math.round((amount * Number(env.PLATFORM_FEE_PERCENT ?? 0)) / 100);
  const registry = env.REGISTRY_URL.replace(/\/$/, "");
  const session = await stripe(env, "POST", "/checkout/sessions", {
    mode: "payment",
    "line_items[0][quantity]": "1",
    "line_items[0][price_data][currency]": currency,
    "line_items[0][price_data][unit_amount]": String(amount),
    "line_items[0][price_data][product_data][name]": `${pack} spec pack`,
    "payment_intent_data[application_fee_amount]": String(fee),
    "payment_intent_data[transfer_data][destination]": seller,
    "metadata[pack]": pack,
    success_url: `${url.origin}/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${registry}/packs/${pack}/`,
  });
  return Response.redirect(session.url, 303);
}

async function success(env, url) {
  const id = url.searchParams.get("session_id") ?? "";
  if (!/^cs_[A-Za-z0-9_]+$/.test(id)) return text("missing session_id", 400);
  const session = await stripe(env, "GET", `/checkout/sessions/${id}`);
  if (session.payment_status !== "paid") return text("payment not completed", 402);
  const pack = session.metadata?.pack;
  let token = await env.LICENSES.get(`session:${id}`);
  if (!token) {
    const bytes = crypto.getRandomValues(new Uint8Array(24));
    token = "sym_" + [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    await env.LICENSES.put(`license:${token}`, JSON.stringify({ pack, session: id }));
    await env.LICENSES.put(`session:${id}`, token);
  }
  const html = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your license</title>
<body style="font: 16px/1.5 system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px">
<h1>Thank you</h1>
<p>Your license for <strong>${escape(pack)}</strong>. Keep it somewhere safe; it is shown once per purchase link.</p>
<pre style="padding: 12px; border: 1px solid #ccc; border-radius: 8px; overflow-x: auto">symbolon pull ${escape(pack)} --token ${escape(token)}</pre>
<p>It covers the latest version of the pack, including future updates.</p></body>`;
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}

async function download(request, env, url) {
  const pack = url.pathname.slice("/download/".length);
  if (!PACK_RE.test(pack)) return text("not found", 404);
  const token = (request.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const license = token ? await env.LICENSES.get(`license:${token}`, "json") : null;
  if (!license || license.pack !== pack) return text("no license for this pack", 403);
  const object = await env.PACKS.get(`packs/${pack}/latest.tar.gz`);
  if (!object) return text("pack tarball not uploaded", 404);
  return new Response(object.body, {
    headers: { "content-type": "application/gzip", "cache-control": "private, no-store" },
  });
}
