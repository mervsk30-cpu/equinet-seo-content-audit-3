/**
 * Live Google rank proxy — Cloudflare Worker.
 *
 * The public dashboard cannot safely contain a SerpAPI key. This Worker keeps
 * the key server-side, searches Google with fixed Singapore settings, and
 * returns only organic positions for equinetacademy.com.
 *
 * Cost controls:
 *  - Fresh results are cached in KV for one hour by default.
 *  - Last-known results remain available when the daily budget is exhausted.
 *  - A Durable Object atomically reserves the daily allowance, so concurrent
 *    requests cannot spend beyond the configured hard ceiling.
 *  - Valid requests are rate-limited per IP by the same coordinator.
 */

const DEFAULTS = {
  GOOGLE_DOMAIN: "google.com.sg",
  COUNTRY: "sg",
  LANGUAGE: "en",
  LOCATION: "Singapore",
  TARGET_DOMAIN: "equinetacademy.com",
  DEPTH: "100",
  CACHE_TTL_SECONDS: "3600",
  STALE_TTL_SECONDS: "2592000",
  DAILY_BUDGET: "500",
  RATE_LIMIT_PER_MIN: "60",
  MAX_KEYWORDS_PER_REQUEST: "25",
  SEARCH_CONCURRENCY: "5",
};

const cfg = (env, key) => env[key] ?? DEFAULTS[key];
const num = (env, key) => parseInt(cfg(env, key), 10);
const boundedInt = (value, fallback, min, max) => {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
};

function allowedOrigins(env) {
  return (env.ALLOWED_ORIGINS || "*").split(",").map(s => s.trim()).filter(Boolean);
}

function originAllowed(env, request) {
  const origin = request.headers.get("Origin");
  const allowed = allowedOrigins(env);
  return !origin || allowed.includes("*") || allowed.includes(origin);
}

function corsHeaders(env, request) {
  const allowed = allowedOrigins(env);
  const origin = request.headers.get("Origin") || "";
  const allow = allowed.includes("*") ? "*" : (allowed.includes(origin) ? origin : "");
  return {
    ...(allow ? { "Access-Control-Allow-Origin": allow } : {}),
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Live-Rank-Token",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

const json = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });

const utcDay = () => new Date().toISOString().slice(0, 10);
const normalise = keyword => keyword.toLowerCase().replace(/\s+/g, " ").trim();
const rankKey = (prefix, keyword, device, env) =>
  `${prefix}:${cfg(env, "GOOGLE_DOMAIN")}:${cfg(env, "LOCATION")}:${device}:${normalise(keyword)}`;
const freshCacheKey = (keyword, device, env) => rankKey("rank", keyword, device, env);
const lastCacheKey = (keyword, device, env) => rankKey("last", keyword, device, env);

/**
 * Strongly consistent coordinator for the daily budget and per-IP rate limit.
 * One object is used per UTC day. Its transaction grants at most the remaining
 * allowance, even when several Worker requests arrive concurrently.
 */
export class LiveRankCoordinator {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    if (request.method !== "POST") return json({ error: "POST only" }, 405);

    let body;
    try { body = await request.json(); } catch { return json({ error: "invalid JSON" }, 400); }

    const requested = boundedInt(body.requested, 0, 0, 1000);
    const dailyLimit = boundedInt(body.daily_limit, 500, 0, 1000000);
    const rateLimit = boundedInt(body.rate_limit, 60, 1, 1000000);
    const rateKey = `rate:${String(body.rate_key || "unknown").slice(0, 300)}`;

    return this.state.storage.transaction(async storage => {
      const hits = boundedInt(await storage.get(rateKey), 0, 0, 1000000);
      const used = boundedInt(await storage.get("used"), 0, 0, dailyLimit);

      if (hits >= rateLimit) {
        return json({
          rate_limited: true,
          granted: 0,
          budget: { used, limit: dailyLimit, remaining: Math.max(0, dailyLimit - used) },
        });
      }

      await storage.put(rateKey, hits + 1);
      const granted = Math.min(requested, Math.max(0, dailyLimit - used));
      const nextUsed = used + granted;
      if (granted) await storage.put("used", nextUsed);

      return json({
        rate_limited: false,
        granted,
        budget: { used: nextUsed, limit: dailyLimit, remaining: Math.max(0, dailyLimit - nextUsed) },
      });
    });
  }
}

async function reserveCapacity(env, request, requested) {
  if (!env.LIVE_RANK_COORDINATOR) {
    throw new Error("LIVE_RANK_COORDINATOR is not configured on the worker");
  }
  const day = utcDay();
  const id = env.LIVE_RANK_COORDINATOR.idFromName(day);
  const stub = env.LIVE_RANK_COORDINATOR.get(id);
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const minute = new Date().toISOString().slice(0, 16);
  const response = await stub.fetch("https://live-rank-coordinator/reserve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      requested,
      daily_limit: num(env, "DAILY_BUDGET"),
      rate_limit: num(env, "RATE_LIMIT_PER_MIN"),
      rate_key: `${minute}:${ip}`,
    }),
  });
  if (!response.ok) throw new Error(`budget coordinator returned ${response.status}`);
  return response.json();
}

/** Run one real Google search and return the target site's organic position. */
async function fetchPosition(keyword, device, env) {
  const depth = num(env, "DEPTH");
  const params = new URLSearchParams({
    engine: "google",
    q: keyword,
    google_domain: cfg(env, "GOOGLE_DOMAIN"),
    gl: cfg(env, "COUNTRY"),
    hl: cfg(env, "LANGUAGE"),
    location: cfg(env, "LOCATION"),
    device,
    num: String(depth),
    filter: "0",
    no_cache: "true",
    api_key: env.SERP_API_KEY,
  });

  const response = await fetch(`https://serpapi.com/search.json?${params}`, {
    cf: { cacheTtl: 0 },
  });
  if (!response.ok) throw new Error(`SERP provider returned ${response.status}`);

  const data = await response.json();
  if (data.error) throw new Error(String(data.error));

  const target = cfg(env, "TARGET_DOMAIN").toLowerCase();
  const organic = Array.isArray(data.organic_results) ? data.organic_results : [];
  for (let index = 0; index < organic.length; index += 1) {
    const result = organic[index];
    let host = "";
    try { host = new URL(result.link).hostname.toLowerCase(); } catch { continue; }
    if (host !== target && !host.endsWith("." + target)) continue;

    const position = typeof result.position === "number" ? result.position : index + 1;
    if (position < 1 || position > depth) break;
    return { position, url: result.link, title: result.title || null };
  }
  return { position: null, url: null, title: null };
}

async function runWithConcurrency(items, concurrency, handler) {
  let cursor = 0;
  const workers = Array.from(
    { length: Math.min(items.length, Math.max(1, concurrency)) },
    async () => {
      while (cursor < items.length) {
        const index = cursor;
        cursor += 1;
        await handler(items[index]);
      }
    },
  );
  await Promise.all(workers);
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(env, request);

    if (!originAllowed(env, request)) return json({ error: "origin not allowed" }, 403, cors);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST") return json({ error: "POST only" }, 405, cors);
    if (env.SHARED_TOKEN && request.headers.get("X-Live-Rank-Token") !== env.SHARED_TOKEN) {
      return json({ error: "unauthorised" }, 401, cors);
    }
    if (!env.SERP_API_KEY) {
      return json({ error: "SERP_API_KEY is not configured on the worker" }, 500, cors);
    }
    if (!env.LIVE_RANK) {
      return json({ error: "LIVE_RANK KV is not configured on the worker" }, 500, cors);
    }

    let body;
    try { body = await request.json(); } catch { return json({ error: "invalid JSON" }, 400, cors); }
    if (!Array.isArray(body.keywords)) return json({ error: "keywords must be an array" }, 400, cors);

    const device = body.device === "mobile" ? "mobile" : "desktop";
    const force = body.force === true;
    const maxKeywords = boundedInt(num(env, "MAX_KEYWORDS_PER_REQUEST"), 25, 1, 50);
    const keywords = [...new Set(body.keywords
      .filter(keyword => typeof keyword === "string" && keyword.trim())
      .map(normalise))].slice(0, maxKeywords);
    if (!keywords.length) return json({ error: "no keywords supplied" }, 400, cors);

    const freshTtl = boundedInt(num(env, "CACHE_TTL_SECONDS"), 3600, 60, 86400);
    const staleTtl = boundedInt(num(env, "STALE_TTL_SECONDS"), 2592000, freshTtl, 31536000);
    const results = {};
    const needFetch = [];

    await Promise.all(keywords.map(async keyword => {
      if (force) {
        needFetch.push(keyword);
        return;
      }
      const hit = await env.LIVE_RANK.get(freshCacheKey(keyword, device, env), { type: "json" });
      if (hit) results[keyword] = { ...hit, cached: true };
      else needFetch.push(keyword);
    }));

    let reservation;
    try {
      reservation = await reserveCapacity(env, request, needFetch.length);
    } catch (error) {
      return json({ error: String(error.message || error) }, 500, cors);
    }
    if (reservation.rate_limited) {
      return json({ error: "rate limited, try again shortly", budget: reservation.budget }, 429, cors);
    }

    const granted = Math.min(needFetch.length, reservation.granted || 0);
    const fetchable = needFetch.slice(0, granted);
    const denied = needFetch.slice(granted);

    await Promise.all(denied.map(async keyword => {
      const stale = await env.LIVE_RANK.get(lastCacheKey(keyword, device, env), { type: "json" });
      results[keyword] = stale
        ? { ...stale, cached: true, stale: true, budget_exceeded: true }
        : { unavailable: true, budget_exceeded: true, device };
    }));

    const concurrency = boundedInt(num(env, "SEARCH_CONCURRENCY"), 5, 1, 6);
    await runWithConcurrency(fetchable, concurrency, async keyword => {
      try {
        const found = await fetchPosition(keyword, device, env);
        const record = { ...found, checked_at: new Date().toISOString(), device };
        const encoded = JSON.stringify(record);
        await Promise.all([
          env.LIVE_RANK.put(freshCacheKey(keyword, device, env), encoded, { expirationTtl: freshTtl }),
          env.LIVE_RANK.put(lastCacheKey(keyword, device, env), encoded, { expirationTtl: staleTtl }),
        ]);
        results[keyword] = { ...record, cached: false };
      } catch (error) {
        results[keyword] = {
          error: String(error.message || error),
          checked_at: new Date().toISOString(),
          device,
        };
      }
    });

    return json({
      checked_at: new Date().toISOString(),
      device,
      settings: {
        google_domain: cfg(env, "GOOGLE_DOMAIN"),
        country: cfg(env, "COUNTRY"),
        language: cfg(env, "LANGUAGE"),
        location: cfg(env, "LOCATION"),
        depth: num(env, "DEPTH"),
        personalization: "off",
        result_type: "organic",
      },
      cache_ttl_seconds: freshTtl,
      budget: { ...reservation.budget, exceeded: denied.length > 0 },
      results,
    }, 200, cors);
  },
};
