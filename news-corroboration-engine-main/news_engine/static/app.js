"use strict";
const $ = (id) => document.getElementById(id);
let apiKey = "", socket, retryTimer, reconnectDelay = 1000;
let feed = new Map();
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
async function api(path, options = {}) {
  const headers = {"Content-Type":"application/json", ...(apiKey ? {"X-API-Key":apiKey} : {})};
  const response = await fetch(path, {...options, headers, signal: AbortSignal.timeout(60000)});
  if (!response.ok) {
    if (response.status === 401) throw new Error("Enter your API key under API access, then connect.");
    if (response.status === 429) throw new Error("Too many requests. Wait a minute before trying again.");
    if (response.status === 503) throw new Error("The server is busy. Please try again shortly.");
    if (response.status === 422) {
      const payload = await response.json().catch(() => ({}));
      const details = Array.isArray(payload.detail) ? payload.detail.map(e => e.msg).join("; ") : payload.detail;
      throw new Error(details || "Enter a name, topic, abbreviation, or claim.");
    }
    throw new Error(`Request failed (${response.status}). Check your input or try again.`);
  }
  return response.json();
}
function timeLabel(date) {
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (!Number.isFinite(seconds)) return "Unknown date";
  if (seconds < 0) return "Future publication time";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
function articleCard(article, match) {
  const card = node("article", undefined, "article");
  const link = node("a", article.title);
  const url = new URL(article.url, location.href);
  if (["https:", "http:"].includes(url.protocol)) link.href = url.href;
  link.target = "_blank"; link.rel = "noopener noreferrer"; link.dir = "auto";
  card.append(link);
  if (article.snippet) {const p = node("p", article.snippet); p.dir="auto"; card.append(p);}
  const meta = node("div", undefined, "meta");
  meta.append(node("span", article.source_name));
  const time = node("time");
  time.dataset.date = article.published_at || article.collected_at;
  time.dataset.prefix = article.published_at ? "Published " : "Collected ";
  time.title = time.dataset.date;
  meta.append(time);
  if (article.flag_level) meta.append(node("span", article.flag_level, `badge ${article.flag_level}`));
  if (match) meta.append(node("span", match.stance === "mention" ? "Search match" : `${match.stance} · ${Math.round(match.score*100)}% similarity`, "badge"));
  if (match && match.retrieved_from === "google_news") meta.append(node("span", "Via Google News", "badge"));
  card.append(meta);
  if (match) card.append(node("p", match.reason));
  return card;
}
function refreshTimes() {
  document.querySelectorAll("time[data-date]").forEach(el => {el.textContent = el.dataset.prefix + timeLabel(el.dataset.date);});
}
function renderFeed() {
  const rows = [...feed.values()].sort((a,b) => new Date(b.published_at || b.collected_at)-new Date(a.published_at || a.collected_at));
  feed = new Map(rows.slice(0,200).map(a => [a.id,a]));
  const visible = rows.filter(a => !$('flagged').checked || a.flag_level).slice(0,50);
  $("feed").replaceChildren(...visible.map(a => articleCard(a)));
  if (!visible.length) $("feed").append(node("p", "No articles yet. Check source health below; the first ingestion may take a minute.", "muted"));
  refreshTimes();
}
async function loadFeed() {
  const articles = await api("/api/articles?limit=200");
  feed = new Map(articles.map(a => [a.id,a])); renderFeed();
}
async function loadSources() {
  const sources = await api("/api/sources");
  $("sources").replaceChildren(...sources.map(s => {
    const el=node("div",s.name,"source");
    el.append(node("span", `${s.status.state.replaceAll("_"," ")}${s.status.mode ? " · " + s.status.mode : ""}${s.status.http_status ? " · HTTP " + s.status.http_status : ""}`));
    if (s.status.checked_at) el.title = `Last checked: ${s.status.checked_at}`;
    return el;
  }));
}
function connectSocket() {
  clearTimeout(retryTimer);
  if (socket) {socket.onclose = null; socket.close();}
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/live-feed`);
  socket.onopen = () => {if(apiKey) socket.send(JSON.stringify({api_key:apiKey}));};
  socket.onmessage = async (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "ready") {
      reconnectDelay = 1000; $("connection").textContent = "● Live feed connected";
      try {await loadFeed();} catch(e) {$("error").textContent=e.message;}
    }
    if (data.type === "article") {feed.set(data.article.id,data.article); renderFeed();}
    if (data.type === "resync_required") {try {await loadFeed();} catch(e) {$("error").textContent=e.message;}}
  };
  socket.onclose = (event) => {
    if (event.code === 1008) {$("connection").textContent="Authentication or origin rejected. Check API access."; return;}
    $("connection").textContent="Live feed disconnected · reconnecting…";
    retryTimer=setTimeout(connectSocket,reconnectDelay); reconnectDelay=Math.min(reconnectDelay*2,30000);
  };
}
$("claim-form").addEventListener("submit", async (event) => {
  event.preventDefault(); $("submit").disabled=true; $("error").textContent="";
  const searchMode = $("query-mode").value === "search";
  $("result").replaceChildren(node("p", searchMode ? "Searching news…" : "Checking recent coverage…", "muted"));
  try {
    const result = await api(searchMode ? "/api/search" : "/api/check", {method:"POST",body:JSON.stringify({claim:$("claim").value, mode:$("query-mode").value, limit:10, days:Number($("search-days").value), live:$("live-search").checked, crime_only:$("crime-only").checked})});
    const box = node("div",undefined,"verdict");
    box.append(node("h2", result.result_label || result.verdict, result.mode === "search" ? "Search" : result.verdict), node("p", result.explanation));
    if (result.mode === "search") {
      box.append(node("small", `${result.matches.length} shown · ${result.indexed_articles} indexed articles searched · Last ${result.days} days`));
      box.append(node("small", `Live search: ${result.live_search.state}`));
      if (result.expanded_terms.length) box.append(node("p", "Related terms: " + result.expanded_terms.map(c=>`${c.name} (${c.terms.join(", ")})`).join("; ")));
      box.append(node("small", result.disclaimer));
    } else {
      const meter=node("progress");meter.max=1;meter.value=result.confidence;meter.setAttribute("aria-label","Retrieval similarity");
      box.append(meter, node("small", `${Math.round(result.confidence*100)}% retrieval similarity · ${result.indexed_articles} indexed articles`));
    }
    if(result.flag_level) box.append(node("p", `Sensitive keywords: ${Object.values(result.matched_keywords).flat().join(", ")}`));
    $("result").replaceChildren(box, ...result.matches.map(m => articleCard(m.article,m)));
    refreshTimes();
  } catch(error) {$("result").replaceChildren(); $("error").textContent=error.message;}
  finally {$("submit").disabled=false;}
});
$("query-mode").addEventListener("change", () => {
  const searchMode = $("query-mode").value === "search";
  $("search-options").hidden = !searchMode;
  $("submit-label").textContent = searchMode ? "Search news" : "Find corroborating coverage";
  $("result").replaceChildren(); $("error").textContent = "";
});
$("flagged").addEventListener("change",renderFeed);
$("connect").addEventListener("click",() => {apiKey=$("api-key").value; $("api-key").value=""; initialize();});
$("history-button").addEventListener("click",async () => {
  try {const rows=await api("/api/history?limit=20");$("history").replaceChildren(...rows.map(r=>node("p",`${r.result.result_label || r.result.verdict} · ${r.result.claim}`)));}
  catch(error) {$("error").textContent=error.message;}
});
async function initialize() {
  $("error").textContent="";
  try {await Promise.all([loadFeed(), loadSources()]);connectSocket();}
  catch(error) {$("error").textContent=error.message;$("connection").textContent="Not connected";}
  try {const health=await api("/health");$("mode").textContent=`Matching: ${health.matching_mode}`;} catch (_) {}
}
setInterval(refreshTimes,1000);
setInterval(()=>loadSources().catch(()=>{}),30000);
initialize();
