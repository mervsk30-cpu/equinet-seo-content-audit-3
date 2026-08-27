import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import worker, { LiveRankCoordinator } from "./live-rank-worker.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

class MemoryKV {
  constructor() { this.values = new Map(); }

  async get(key, options = {}) {
    const value = this.values.get(key);
    if (value == null) return null;
    return options.type === "json" ? JSON.parse(value) : value;
  }

  async put(key, value) { this.values.set(key, value); }
}

class TransactionalStorage {
  constructor() {
    this.values = new Map();
    this.queue = Promise.resolve();
  }

  async get(key) { return this.values.get(key); }
  async put(key, value) { this.values.set(key, value); }

  transaction(handler) {
    const run = this.queue.then(() => handler(this));
    this.queue = run.then(() => undefined, () => undefined);
    return run;
  }
}

class CoordinatorNamespace {
  constructor() { this.instances = new Map(); }
  idFromName(name) { return name; }

  get(id) {
    if (!this.instances.has(id)) {
      const state = { storage: new TransactionalStorage() };
      this.instances.set(id, new LiveRankCoordinator(state));
    }
    const instance = this.instances.get(id);
    return {
      fetch(input, init) {
        const request = input instanceof Request ? input : new Request(input, init);
        return instance.fetch(request);
      },
    };
  }
}

function makeEnv(overrides = {}) {
  return {
    SERP_API_KEY: "test-secret-never-log",
    LIVE_RANK: new MemoryKV(),
    LIVE_RANK_COORDINATOR: new CoordinatorNamespace(),
    ALLOWED_ORIGINS: "https://mervsk30-cpu.github.io",
    DAILY_BUDGET: "500",
    RATE_LIMIT_PER_MIN: "60",
    MAX_KEYWORDS_PER_REQUEST: "25",
    SEARCH_CONCURRENCY: "5",
    ...overrides,
  };
}

function request(keywords, options = {}) {
  return new Request("https://equinet-live-rank.test/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Origin": options.origin || "https://mervsk30-cpu.github.io",
      "CF-Connecting-IP": options.ip || "203.0.113.10",
    },
    body: JSON.stringify({ keywords, device: options.device || "desktop", force: options.force === true }),
  });
}

function providerResult(organicResults) {
  return new Response(JSON.stringify({ organic_results: organicResults }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

test("returns an exact organic position with pinned Singapore settings", async () => {
  const env = makeEnv();
  let providerUrl;
  globalThis.fetch = async url => {
    providerUrl = new URL(url);
    return providerResult([
      { position: 1, link: "https://example.com/", title: "Other" },
      { position: 2, link: "https://www.equinetacademy.com/course/seo-training-course-singapore/", title: "SEO Course" },
    ]);
  };

  const response = await worker.fetch(request(["SEO Course Singapore"]), env);
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.results["seo course singapore"].position, 2);
  assert.match(body.results["seo course singapore"].checked_at, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(body.settings.google_domain, "google.com.sg");
  assert.equal(body.settings.country, "sg");
  assert.equal(body.settings.language, "en");
  assert.equal(body.settings.location, "Singapore");
  assert.equal(body.settings.depth, 100);
  assert.equal(body.settings.personalization, "off");
  assert.equal(body.settings.result_type, "organic");
  assert.equal(providerUrl.searchParams.get("google_domain"), "google.com.sg");
  assert.equal(providerUrl.searchParams.get("gl"), "sg");
  assert.equal(providerUrl.searchParams.get("hl"), "en");
  assert.equal(providerUrl.searchParams.get("location"), "Singapore");
  assert.equal(providerUrl.searchParams.get("device"), "desktop");
  assert.equal(providerUrl.searchParams.get("num"), "100");
  assert.equal(providerUrl.searchParams.get("filter"), "0");
  assert.equal(providerUrl.searchParams.get("no_cache"), "true");
  assert.equal(providerUrl.searchParams.get("api_key"), env.SERP_API_KEY);
});

test("reports not in top 100 as null and never guesses", async () => {
  const env = makeEnv();
  globalThis.fetch = async () => providerResult([
    { position: 1, link: "https://example.com/", title: "Other" },
  ]);

  const response = await worker.fetch(request(["unranked keyword"]), env);
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.results["unranked keyword"].position, null);
  assert.equal(body.results["unranked keyword"].url, null);
});

test("serves repeat checks from the one-hour cache without another provider call", async () => {
  const env = makeEnv();
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return providerResult([{ position: 3, link: "https://equinetacademy.com/course/test/" }]);
  };

  const first = await (await worker.fetch(request(["cached keyword"]), env)).json();
  const second = await (await worker.fetch(request(["cached keyword"]), env)).json();

  assert.equal(calls, 1);
  assert.equal(first.results["cached keyword"].cached, false);
  assert.equal(second.results["cached keyword"].cached, true);
  assert.equal(second.results["cached keyword"].checked_at, first.results["cached keyword"].checked_at);
  assert.equal(second.budget.used, 1);
});

test("serves a stale last-known result and an explicit unavailable state at the daily cap", async () => {
  const env = makeEnv({ DAILY_BUDGET: "1" });
  globalThis.fetch = async () => providerResult([
    { position: 4, link: "https://equinetacademy.com/course/test/" },
  ]);

  const first = await (await worker.fetch(request(["known keyword"]), env)).json();
  const stale = await (await worker.fetch(request(["known keyword"], { force: true }), env)).json();
  const unavailable = await (await worker.fetch(request(["new keyword"]), env)).json();

  assert.equal(first.budget.used, 1);
  assert.equal(stale.results["known keyword"].position, 4);
  assert.equal(stale.results["known keyword"].stale, true);
  assert.equal(stale.results["known keyword"].checked_at, first.results["known keyword"].checked_at);
  assert.equal(stale.budget.exceeded, true);
  assert.equal(unavailable.results["new keyword"].unavailable, true);
  assert.equal(unavailable.results["new keyword"].budget_exceeded, true);
});

test("enforces the hard daily cap atomically across concurrent requests", async () => {
  const env = makeEnv({ DAILY_BUDGET: "1" });
  let providerCalls = 0;
  globalThis.fetch = async () => {
    providerCalls += 1;
    return providerResult([{ position: 5, link: "https://equinetacademy.com/course/test/" }]);
  };

  const [firstResponse, secondResponse] = await Promise.all([
    worker.fetch(request(["first concurrent keyword"], { ip: "203.0.113.11" }), env),
    worker.fetch(request(["second concurrent keyword"], { ip: "203.0.113.12" }), env),
  ]);
  const bodies = await Promise.all([firstResponse.json(), secondResponse.json()]);
  const values = bodies.map(body => Object.values(body.results)[0]);

  assert.equal(providerCalls, 1);
  assert.equal(values.filter(value => value.position === 5).length, 1);
  assert.equal(values.filter(value => value.unavailable === true).length, 1);
  assert.equal(Math.max(...bodies.map(body => body.budget.used)), 1);
});

test("rate-limits valid requests per IP and minute", async () => {
  const env = makeEnv({ RATE_LIMIT_PER_MIN: "1" });
  globalThis.fetch = async () => providerResult([
    { position: 6, link: "https://equinetacademy.com/course/test/" },
  ]);

  const first = await worker.fetch(request(["rate keyword"]), env);
  const second = await worker.fetch(request(["rate keyword"]), env);
  const secondBody = await second.json();

  assert.equal(first.status, 200);
  assert.equal(second.status, 429);
  assert.equal(secondBody.error, "rate limited, try again shortly");
});

test("returns provider failures as explicit per-keyword errors with timestamps", async () => {
  const env = makeEnv();
  globalThis.fetch = async () => new Response("upstream unavailable", { status: 503 });

  const response = await worker.fetch(request(["provider error keyword"]), env);
  const body = await response.json();
  const result = body.results["provider error keyword"];

  assert.equal(response.status, 200);
  assert.match(result.error, /503/);
  assert.match(result.checked_at, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal("position" in result, false);
});

test("bounds provider concurrency for a multi-keyword batch", async () => {
  const env = makeEnv({ SEARCH_CONCURRENCY: "3" });
  let active = 0;
  let peak = 0;
  globalThis.fetch = async () => {
    active += 1;
    peak = Math.max(peak, active);
    await new Promise(resolve => setTimeout(resolve, 5));
    active -= 1;
    return providerResult([]);
  };

  const keywords = Array.from({ length: 9 }, (_, index) => `batch keyword ${index}`);
  const response = await worker.fetch(request(keywords), env);
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(Object.keys(body.results).length, 9);
  assert.equal(peak, 3);
});

test("rejects disallowed origins and malformed keyword payloads", async () => {
  const env = makeEnv();
  globalThis.fetch = async () => { throw new Error("provider should not be called"); };

  const wrongOrigin = await worker.fetch(request(["keyword"], { origin: "https://evil.example" }), env);
  const malformed = await worker.fetch(new Request("https://equinet-live-rank.test/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Origin": "https://mervsk30-cpu.github.io" },
    body: JSON.stringify({ keywords: "not-an-array" }),
  }), env);

  assert.equal(wrongOrigin.status, 403);
  assert.equal(wrongOrigin.headers.get("Access-Control-Allow-Origin"), null);
  assert.equal(malformed.status, 400);
  assert.deepEqual(await malformed.json(), { error: "keywords must be an array" });
});
