#!/usr/bin/env node
/**
 * Mock live-rank proxy for LOCAL UI TESTING ONLY.
 *
 * Speaks the same contract as live-rank-worker.js but performs no Google search
 * and costs nothing. Positions are derived from a hash of the keyword so they
 * are stable between runs.
 *
 * These numbers are FAKE and every response is flagged `"mock": true` so they
 * can never be mistaken for real ranking data. The published dashboard talks to
 * the real Worker; this exists so the front-end can be exercised without
 * burning SERP API credits.
 *
 *   node serverless/mock-live-rank.js [port]
 */
const http = require("http");

const PORT = parseInt(process.argv[2] || "8787", 10);
const norm = k => k.toLowerCase().replace(/\s+/g, " ").trim();

function fakePosition(keyword) {
  let h = 0;
  for (let i = 0; i < keyword.length; i++) h = (h * 31 + keyword.charCodeAt(i)) >>> 0;
  if (h % 11 === 0) return null;            // ~9% "not in top 100"
  return (h % 40) + 1;
}

http.createServer((req, res) => {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Live-Rank-Token",
  };
  if (req.method === "OPTIONS") { res.writeHead(204, cors); return res.end(); }
  if (req.method !== "POST") { res.writeHead(405, cors); return res.end("POST only"); }

  let raw = "";
  req.on("data", c => (raw += c));
  req.on("end", () => {
    let body = {};
    try { body = JSON.parse(raw); } catch {}
    const device = body.device === "mobile" ? "mobile" : "desktop";
    const keywords = [...new Set((body.keywords || []).map(norm))].slice(0, 100);
    const now = new Date().toISOString();
    const results = {};
    for (const kw of keywords) {
      const position = fakePosition(kw + device);
      results[kw] = {
        position,
        url: position ? "https://www.equinetacademy.com/course/mock/" : null,
        title: position ? "Mock result" : null,
        checked_at: now, device, cached: false, mock: true,
      };
    }
    res.writeHead(200, { ...cors, "Content-Type": "application/json" });
    res.end(JSON.stringify({
      checked_at: now, device, mock: true,
      settings: { google_domain: "google.com.sg", country: "sg", language: "en", location: "Singapore", depth: 100 },
      cache_ttl_seconds: 3600,
      budget: { used: keywords.length, limit: 500, remaining: 500 - keywords.length, exceeded: false },
      results,
    }));
  });
}).listen(PORT, () => console.log(`mock live-rank proxy on http://localhost:${PORT} (FAKE data)`));
