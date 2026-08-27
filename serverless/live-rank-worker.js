/**
 * Live Google rank proxy — Cloudflare Worker.
 *
 * WHY THIS EXISTS
 * The dashboard is a static page on a PUBLIC repo and a PUBLIC Pages site, so
 * it cannot hold a SERP API key (it would be readable in the page source, and
 * browsers would block the cross-origin call anyway). This Worker holds the key
 * server-side, runs the search, and returns only a position number.
 *
 * WHAT IT GUARANTEES
 *  - Results comparable to a manual Google search from Singapore: fixed
 *    google_domain / gl / hl / location / device, personalisation off.
 *  - Cost control, which is the real risk when a page fetches live ranks on
 *    open. Three independent brakes:
 *      1. CACHE_TTL_SECONDS  - repeat views inside the window cost nothing.
 *      2. DAILY_BUDGET       - a hard ceiling on paid searches per UTC day.
 *                              Past it, cached values are still served (clearly
 *                              flagged) but no new searches are billed.
 *      3. RATE_LIMIT_*       - stops the public endpoint being hammered.
 *  - It never invents a position. No result => position null => the dashboard
 *    shows "not in top N", never a guess.
 *
 * DEPLOY: see serverless/README.md
 */

const DEFAULTS = {
  GOOGLE_DOMAIN: "google.com.sg",
  COUNTRY: "sg",
  LANGUAGE: "en",
  LOCATION: "Singapore",
  TARGET_DOMAIN: "equinetacademy.com",
  DEPTH: "100",            // how deep to look before reporting "not found"
  CACHE_TTL_SECONDS: "3600",
  DAILY_BUDGET: "500",     // paid searches per UTC day, hard stop
  RATE_LIMIT_PER_MIN: "60",
  MAX_KEYWORDS_PER_REQUEST: "100",
};

const cfg = (env, key) => env[key] ?? DEFAULTS[key];
const num = (env, key) => parseInt(cfg(env, key), 10);

function corsHeaders(env, request) {
  const allowed = (env.ALLOWED_ORIGINS || "*").split(",").map(s => s.trim()).filter(Boolean);
  const origin = request.headers.get("Origin") || "";
  const allow = allowed.includes("*") ? "*" : (allowed.includes(origin) ? origin : allowed[0] || "");
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Live-Rank-Token",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

const json = (body, status, headers) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });

const utcDay = () => new Date().toISOString().slice(0, 10);
const normalise = k => k.toLowerCase().replace(/\s+/g, " ").trim();
const cacheKey = (kw, device, env) =>
  `rank:${cfg(env, "GOOGLE_DOMAIN")}:${cfg(env, "LOCATION")}:${device}:${normalise(kw)}`;

/** Count a paid search against today's budget. Returns false when exhausted. */
async function claimBudget(env, n) {
  const limit = num(env, "DAILY_BUDGET");
  const key = `budget:${utcDay()}`;
  const used = parseInt((await env.LIVE_RANK.get(key)) || "0", 10);
  if (used + n > limit) return false;
  // 48h expiry so the counter self-cleans
  await env.LIVE_RANK.put(key, String(used + n), { expirationTtl: 172800 });
  return true;
}

async function budgetState(env) {
  const limit = num(env, "DAILY_BUDGET");
  const used = parseInt((await env.LIVE_RANK.get(`budget:${utcDay()}`)) || "0", 10);
  return { used, limit, remaining: Math.max(0, limit - used) };
}

async function rateLimited(env, request) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const minute = new Date().toISOString().slice(0, 16);
  const key = `rl:${ip}:${minute}`;
  const hits = parseInt((await env.LIVE_RANK.get(key)) || "0", 10);
  if (hits >= num(env, "RATE_LIMIT_PER_MIN")) return true;
  await env.LIVE_RANK.put(key, String(hits + 1), { expirationTtl: 120 });
  return false;
}

/**
 * Run one real Google search and return the target site's ORGANIC position.
 *
 * Organic position is what Ahrefs reports and what "what do we rank" means.
 * Ads, local packs and AI overviews are excluded, so a manual search may show
 * our result lower on the page than this number implies - that is expected and
 * is explained in the dashboard.
 */
async function fetchPosition(keyword, device, env) {
  const params = new URLSearchParams({
    engine: "google",
    q: keyword,
    google_domain: cfg(env, "GOOGLE_DOMAIN"),
    gl: cfg(env, "COUNTRY"),
    hl: cfg(env, "LANGUAGE"),
    location: cfg(env, "LOCATION"),
    device,
    num: cfg(env, "DEPTH"),
    filter: "0",     // do not collapse near-duplicate results
    no_cache: "true", // we run our own cache; never bill for a stale provider hit
    api_key: env.SERP_API_KEY,
  });

  const resp = await fetch(`https://serpapi.com/search.json?${params}`, {
    cf: { cacheTtl: 0 },
  });
  if (!resp.ok) {
    throw new Error(`SERP provider returned ${resp.status}`);
  }
  const data = await resp.json();
  if (data.error) throw new Error(String(data.error));

  const target = cfg(env, "TARGET_DOMAIN").toLowerCase();
  const organic = Array.isArray(data.organic_results) ? data.organic_results : [];
  for (const r of organic) {
    let host = "";
    try { host = new URL(r.link).hostname.toLowerCase(); } catch { continue; }
    if (host === target || host.endsWith("." + target)) {
      return {
        // trust the provider's own position field when present; fall back to order
        position: typeof r.position === "number" ? r.position : organic.indexOf(r) + 1,
        url: r.link,
        title: r.title || null,
      };
    }
  }
  return { position: null, url: null, title: null }; // genuinely not in the top N
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(env, request);

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST") return json({ error: "POST only" }, 405, cors);

    if (env.SHARED_TOKEN && request.headers.get("X-Live-Rank-Token") !== env.SHARED_TOKEN) {
      return json({ error: "unauthorised" }, 401, cors);
    }
    if (!env.SERP_API_KEY) {
      return json({ error: "SERP_API_KEY is not configured on the worker" }, 500, cors);
    }
    if (await rateLimited(env, request)) {
      return json({ error: "rate limited, try again shortly" }, 429, cors);
    }

    let body;
    try { body = await request.json(); } catch { return json({ error: "invalid JSON" }, 400, cors); }

    const device = body.device === "mobile" ? "mobile" : "desktop";
    const force = body.force === true;
    const maxKw = num(env, "MAX_KEYWORDS_PER_REQUEST");
    const keywords = [...new Set((body.keywords || [])
      .filter(k => typeof k === "string" && k.trim())
      .map(normalise))].slice(0, maxKw);

    if (!keywords.length) return json({ error: "no keywords supplied" }, 400, cors);

    const ttl = num(env, "CACHE_TTL_SECONDS");
    const results = {};
    const needFetch = [];

    // 1) serve from cache first - this is what makes "fetch on open" affordable
    for (const kw of keywords) {
      if (force) { needFetch.push(kw); continue; }
      const hit = await env.LIVE_RANK.get(cacheKey(kw, device, env), { type: "json" });
      if (hit) results[kw] = { ...hit, cached: true };
      else needFetch.push(kw);
    }

    // 2) spend budget only on what is genuinely missing
    let budgetExceeded = false;
    for (const kw of needFetch) {
      if (!(await claimBudget(env, 1))) {
        budgetExceeded = true;
        const stale = await env.LIVE_RANK.get(cacheKey(kw, device, env), { type: "json" });
        if (stale) results[kw] = { ...stale, cached: true, stale: true };
        continue; // never bill past the ceiling
      }
      try {
        const found = await fetchPosition(kw, device, env);
        const record = { ...found, checked_at: new Date().toISOString(), device };
        await env.LIVE_RANK.put(cacheKey(kw, device, env), JSON.stringify(record), { expirationTtl: ttl });
        results[kw] = { ...record, cached: false };
      } catch (err) {
        results[kw] = { error: String(err.message || err), checked_at: new Date().toISOString(), device };
      }
    }

    return json({
      checked_at: new Date().toISOString(),
      device,
      settings: {
        google_domain: cfg(env, "GOOGLE_DOMAIN"),
        country: cfg(env, "COUNTRY"),
        language: cfg(env, "LANGUAGE"),
        location: cfg(env, "LOCATION"),
        depth: num(env, "DEPTH"),
      },
      cache_ttl_seconds: ttl,
      budget: { ...(await budgetState(env)), exceeded: budgetExceeded },
      results,
    }, 200, cors);
  },
};
