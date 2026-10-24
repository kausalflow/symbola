// The Symbolon store: sells priced packs from the static registry.
//
//   POST /checkout              form or JSON {pack}: start a Stripe Checkout for that pack
//   POST /webhook               Stripe events: issue a license on payment, revoke it on refund or dispute
//   GET  /success?session_id=   after payment: show the license the webhook issued
//   GET  /download/<owner>/<name>   with "Authorization: Bearer <token>": the pack's latest tarball
//
// Prices come from the registry's public index.json, so the site and the store
// never disagree. Payment goes to the seller's Stripe Connect account, minus the
// platform fee. Licenses cover the pack's latest version, the only one served.
// The webhook is the only place a license is issued, so a buyer who closes the
// tab before the success page still has one, tied to their Checkout email.
//
// Bindings (wrangler.toml): LICENSES (KV), PACKS (R2), REGISTRY_URL,
// PLATFORM_FEE_PERCENT; secrets STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET.
// KV keys: seller:<owner> -> Stripe account id;
// license:<token> -> {pack, session, email, payment_intent, issued, revoked?};
// session:<checkout session id> -> token; payment:<payment intent id> -> token;
// buyer:<email>:<pack> -> token (support looks a buyer up by email).

const STRIPE = "https://api.stripe.com/v1";
const PACK_RE = /^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9-]*$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (request.method === "POST" && url.pathname === "/checkout") return await checkout(request, env, url);
      if (request.method === "POST" && url.pathname === "/webhook") return await webhook(request, env);
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

const SIGNATURE_TOLERANCE_SECONDS = 300;

async function hmacHex(secret, message) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sameString(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** Check Stripe's `Stripe-Signature` header (t=…,v1=…) over the raw body. */
export async function verifyStripeSignature(body, header, secret, now = Date.now() / 1000) {
  const items = (header ?? "").split(",").map((p) => p.trim().split("="));
  const t = Number(items.find(([k]) => k === "t")?.[1]);
  const sigs = items.filter(([k]) => k === "v1").map(([, v]) => v ?? "");
  if (!secret || !t || !sigs.length || Math.abs(now - t) > SIGNATURE_TOLERANCE_SECONDS) return false;
  const expected = await hmacHex(secret, `${t}.${body}`);
  return sigs.some((s) => sameString(s, expected));
}

async function webhook(request, env) {
  const body = await request.text();
  if (!(await verifyStripeSignature(body, request.headers.get("stripe-signature"), env.STRIPE_WEBHOOK_SECRET))) {
    return text("bad signature", 400);
  }
  const event = JSON.parse(body);
  const object = event.data?.object ?? {};
  if (event.type === "checkout.session.completed" || event.type === "checkout.session.async_payment_succeeded") {
    if (object.payment_status === "paid") await issue(env, object);
  } else if (event.type === "charge.refunded" || event.type === "charge.dispute.created") {
    const intent = object.payment_intent;
    const token = intent && await env.LICENSES.get(`payment:${intent}`);
    if (token) {
      const license = await env.LICENSES.get(`license:${token}`, "json");
      await env.LICENSES.put(`license:${token}`, JSON.stringify({ ...license, revoked: event.type }));
    }
  }
  return text("ok");
}

async function issue(env, session) {
  if (await env.LICENSES.get(`session:${session.id}`)) return; // Stripe retries; issue once
  const pack = session.metadata?.pack;
  if (!PACK_RE.test(pack ?? "")) return;
  const email = (session.customer_details?.email ?? "").toLowerCase();
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  const token = "sym_" + [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  const license = { pack, session: session.id, email, payment_intent: session.payment_intent ?? null,
                    issued: new Date().toISOString() };
  await env.LICENSES.put(`license:${token}`, JSON.stringify(license));
  await env.LICENSES.put(`session:${session.id}`, token);
  if (license.payment_intent) await env.LICENSES.put(`payment:${license.payment_intent}`, token);
  if (email) await env.LICENSES.put(`buyer:${email}:${pack}`, token);
}

async function success(env, url) {
  const id = url.searchParams.get("session_id") ?? "";
  if (!/^cs_[A-Za-z0-9_]+$/.test(id)) return text("missing session_id", 400);
  const token = await env.LICENSES.get(`session:${id}`);
  const license = token ? await env.LICENSES.get(`license:${token}`, "json") : null;
  const page = (title, inner) => new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<body style="font: 16px/1.5 system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px">${inner}</body>`,
    { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
  if (!license) {
    return page("Payment processing", `<h1>Almost there</h1>
<p>Your payment is being confirmed. Reload this page in a few seconds to see your license.
If you close it, the license is kept under the email you paid with.</p>`);
  }
  return page("Your license", `<h1>Thank you</h1>
<p>Your license for <strong>${escape(license.pack)}</strong>${license.email ? `, kept under ${escape(license.email)}` : ""}.
Keep it somewhere safe.</p>
<pre style="padding: 12px; border: 1px solid #ccc; border-radius: 8px; overflow-x: auto">symbolon pull ${escape(license.pack)} --token ${escape(token)}</pre>
<p>It covers the latest version of the pack, including future updates.</p>`);
}

async function download(request, env, url) {
  const pack = url.pathname.slice("/download/".length);
  if (!PACK_RE.test(pack)) return text("not found", 404);
  const token = (request.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const license = token ? await env.LICENSES.get(`license:${token}`, "json") : null;
  if (!license || license.pack !== pack) return text("no license for this pack", 403);
  if (license.revoked) return text("this license was revoked after a refund or dispute", 403);
  const object = await env.PACKS.get(`packs/${pack}/latest.tar.gz`);
  if (!object) return text("pack tarball not uploaded", 404);
  return new Response(object.body, {
    headers: { "content-type": "application/gzip", "cache-control": "private, no-store" },
  });
}
