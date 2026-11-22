// 神社マップ MCP サーバー（Cloudflare Workers 用・読み取り専用・依存なし）
// 地図サイトが公開しているデータ（JSON）を読んで、AI アプリから神社を検索できるようにする。
const DATA_BASE = "https://yoheionozato.github.io/jinja-map/data/";
const SITE = "https://yoheionozato.github.io/jinja-map/";
const CELL = 0.25;
const RANK = { 6: "一宮・二十二社", 5: "名神大社・官幣大社級", 4: "別表神社級", 3: "式内社・県社級", 2: "郷社・村社級／記事あり", 1: "" };
const CREDIT = "出典：位置・名称 OpenStreetMap © OpenStreetMap contributors (ODbL)／由来・祭神 Wikipedia (CC BY-SA)。社格・系統・時代は機械的な読み取りで誤りを含みます。" + SITE;

let coreCache = null;
const detailCache = new Map();

async function getJson(env, path) {
  const base = (env && env.DATA_BASE) || DATA_BASE;
  const r = await fetch(base + path, { cf: { cacheTtl: 3600, cacheEverything: true } });
  if (r.status === 404) return {};
  if (!r.ok) throw new Error("データを取得できませんでした: " + path + " (" + r.status + ")");
  return r.json();
}
async function core(env) {
  if (!coreCache) coreCache = getJson(env, "core_s.json").catch(e => { coreCache = null; throw e; });
  return coreCache;
}
async function detailOf(env, c, i) {
  const cell = Math.floor(c.y[i] / 1e5 / CELL) + "_" + Math.floor(c.x[i] / 1e5 / CELL);
  if (!detailCache.has(cell)) detailCache.set(cell, getJson(env, "detail_s/" + cell + ".json").catch(() => ({})));
  return ((await detailCache.get(cell))[String(i)]) || {};
}
const norm = s => String(s || "").normalize("NFKC").replace(/[\s・･]/g, "").toLowerCase();
function dist(lat1, lon1, lat2, lon2) {
  const R = 6371000, r = Math.PI / 180, dl = (lat2 - lat1) * r, dn = (lon2 - lon1) * r;
  const a = Math.sin(dl / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dn / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
function brief(c, i) {
  return { 名前: c.n[i], 都県: c.p[i] ? c.prefs[c.p[i] - 1] : "", 社格: RANK[c.r[i]] || "", 系統: c.kinds[c.k[i]] === "その他" ? "" : c.kinds[c.k[i]],
    緯度: c.y[i] / 1e5, 経度: c.x[i] / 1e5, 地図: SITE + "#17/" + (c.y[i] / 1e5).toFixed(5) + "/" + (c.x[i] / 1e5).toFixed(5) };
}
async function full(env, c, i) {
  const o = brief(c, i), d = await detailOf(env, c, i);
  if (d.rl) o.社格 = d.rl;
  if (d.a) o.所在地 = d.a;
  if (d.d) o.主祭神 = d.d;
  if (d.f) o.創建 = d.f;
  if (d.in) o.概要 = d.in;
  if (d.h) o.由来 = d.h.length > 600 ? d.h.slice(0, 600) + "…（続きは地図サイトで）" : d.h;
  if (d.ev) o.行事 = d.ev.map(e => e.n + (e.d ? "：" + e.d : "") + (e.u ? "（出典 " + e.u + "）" : ""));
  const pp = c.pp[String(i)];
  if (pp && (pp[0].length || pp[1].length)) o.ゆかりの人物 = [...new Set([...pp[0], ...pp[1]])].slice(0, 12);
  return o;
}

const TOOLS = [
  { name: "search_shrines", description: "名前（一部でも可）で神社を探す。例：「貫前」「赤城神社」。都県で絞り込める。上位の結果には祭神・創建・由来・行事などの詳細も付く。",
    inputSchema: { type: "object", properties: { query: { type: "string", description: "神社名の一部" }, prefecture: { type: "string", description: "例：群馬県（省略可）" }, limit: { type: "integer", description: "最大件数（既定5、最大20）" } }, required: ["query"] } },
  { name: "nearby_shrines", description: "指定した緯度・経度の近くにある神社を、近い順に返す。「この近くの神社」に使う。",
    inputSchema: { type: "object", properties: { lat: { type: "number" }, lon: { type: "number" }, radius_km: { type: "number", description: "半径km（既定3、最大30）" }, limit: { type: "integer", description: "最大件数（既定8、最大30）" }, min_rank: { type: "integer", description: "社格の下限 1〜6（省略可。3以上で式内社・県社級以上）" } }, required: ["lat", "lon"] } },
  { name: "shrines_by_person", description: "祭神や、由来に名前が出る人物（例：徳川家康、菅原道真、日本武尊）にゆかりのある神社を探す。",
    inputSchema: { type: "object", properties: { person: { type: "string" }, prefecture: { type: "string" }, limit: { type: "integer" } }, required: ["person"] } },
];

async function callTool(env, name, a) {
  const c = await core(env);
  const n = c.n.length;
  const lim = (v, d, m) => Math.max(1, Math.min(m, Math.floor(v || d)));
  if (name === "search_shrines") {
    const q = norm(a.query), pf = a.prefecture ? norm(a.prefecture) : "";
    const hits = [];
    for (let i = 0; i < n; i++) {
      if (!c.n[i] || c.n[i].startsWith("（") || !norm(c.n[i]).includes(q)) continue;
      if (pf && !norm(c.p[i] ? c.prefs[c.p[i] - 1] : "").includes(pf)) continue;
      hits.push(i);
    }
    hits.sort((x, y) => c.r[y] - c.r[x]);
    const L = lim(a.limit, 5, 20), top = hits.slice(0, L);
    const res = [];
    for (let k = 0; k < top.length; k++) res.push(k < 5 ? await full(env, c, top[k]) : brief(c, top[k]));
    return { 該当件数: hits.length, 結果: res, 出典: CREDIT };
  }
  if (name === "nearby_shrines") {
    const R = Math.min(30, a.radius_km || 3) * 1000, mr = a.min_rank || 1, hits = [];
    for (let i = 0; i < n; i++) {
      if (c.r[i] < mr || !c.n[i] || c.n[i].startsWith("（")) continue;
      const d = dist(a.lat, a.lon, c.y[i] / 1e5, c.x[i] / 1e5);
      if (d <= R) hits.push([d, i]);
    }
    hits.sort((x, y) => x[0] - y[0]);
    const top = hits.slice(0, lim(a.limit, 8, 30));
    const res = [];
    for (let k = 0; k < top.length; k++) { const o = k < 3 ? await full(env, c, top[k][1]) : brief(c, top[k][1]); o.距離m = Math.round(top[k][0]); res.push(o); }
    return { 該当件数: hits.length, 結果: res, 出典: CREDIT };
  }
  if (name === "shrines_by_person") {
    const q = norm(a.person), pf = a.prefecture ? norm(a.prefecture) : "", hits = [];
    for (const k of Object.keys(c.pp)) {
      const i = +k, pp = c.pp[k], names = [...pp[0], ...pp[1]];
      if (!names.some(x => norm(x).includes(q))) continue;
      if (pf && !norm(c.p[i] ? c.prefs[c.p[i] - 1] : "").includes(pf)) continue;
      hits.push([pp[0].some(x => norm(x).includes(q)) ? 1 : 0, i]);
    }
    hits.sort((x, y) => y[0] - x[0] || c.r[y[1]] - c.r[x[1]]);
    const top = hits.slice(0, lim(a.limit, 8, 30));
    const res = top.map(([isDeity, i]) => ({ ...brief(c, i), 関係: isDeity ? "祭神" : "由来に登場" }));
    return { 該当件数: hits.length, 結果: res, 出典: CREDIT };
  }
  throw new Error("不明なツール: " + name);
}

const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "content-type, mcp-protocol-version, mcp-session-id", "access-control-allow-methods": "POST, GET, OPTIONS" };
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", ...CORS } });

async function rpc(env, m) {
  const id = m.id;
  const ok = result => ({ jsonrpc: "2.0", id, result });
  const err = (code, message) => ({ jsonrpc: "2.0", id, error: { code, message } });
  if (m.method === "initialize")
    return ok({ protocolVersion: (m.params && m.params.protocolVersion) || "2025-03-26", capabilities: { tools: {} }, serverInfo: { name: "jinja-map", version: "0.1.0" },
      instructions: "関東の神社データベース。名前検索・近くの神社・人物ゆかりの神社が使える。回答には出典（OpenStreetMap・Wikipedia）を添えること。" });
  if (m.method === "ping") return ok({});
  if (m.method === "tools/list") return ok({ tools: TOOLS });
  if (m.method === "tools/call") {
    try {
      const r = await callTool(env, m.params.name, m.params.arguments || {});
      return ok({ content: [{ type: "text", text: JSON.stringify(r, null, 1) }] });
    } catch (e) { return ok({ isError: true, content: [{ type: "text", text: String(e.message || e) }] }); }
  }
  if (id === undefined) return null; // 通知
  return err(-32601, "未対応のメソッド: " + m.method);
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (req.method === "GET") return json({ name: "jinja-map MCP", usage: "POST JSON-RPC (Streamable HTTP, 状態なし)", site: SITE });
    if (req.method !== "POST") return json({ error: "method not allowed" }, 405);
    let body;
    try { body = await req.json(); } catch { return json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "JSON が不正です" } }, 400); }
    if (Array.isArray(body)) {
      const out = (await Promise.all(body.map(m => rpc(env, m)))).filter(Boolean);
      return out.length ? json(out) : new Response(null, { status: 202, headers: CORS });
    }
    const out = await rpc(env, body);
    return out ? json(out) : new Response(null, { status: 202, headers: CORS });
  },
};
