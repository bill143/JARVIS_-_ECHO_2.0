/* JARVIS Command Console — live client. All text is rendered with textContent. */
"use strict";

const TOKEN = document.querySelector('meta[name="jarvis-token"]').content;
const $ = (id) => document.getElementById(id);
const WAVE_BARS = 36;
const RECONNECT_MAX_MS = 8000;

const ui = {
  state: "starting",
  muted: false,
  micLevel: 0,
  botLevel: 0,
  streamingReply: null,
  unreadConversation: 0,
  config: {},
  health: {},
};

// ---------------------------------------------------------------- api
async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-JARVIS-Token": TOKEN, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({ success: false, error: { message: `HTTP ${res.status}` } }));
  if (!json.success) throw new Error(json.error?.message || `HTTP ${res.status}`);
  return json.data;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ---------------------------------------------------------------- transcript
const LABELS = { user: "You", reply: "JARVIS", heard: "Heard (ignored)", tool: "Tool", seen: "Saw", error: "Error", interrupted: "Stopped" };

function addMessage(kind, text, ts, extra) {
  const list = $("transcript");
  const item = el("li", `msg ${kind}`);
  const meta = el("div", "meta");
  meta.append(el("span", "", extra?.label || LABELS[kind] || kind), el("time", "", fmtTime(ts || Date.now() / 1000)));
  item.append(meta, el("div", "body", text));
  list.append(item);
  while (list.children.length > 300) list.firstElementChild.remove();
  list.scrollTop = list.scrollHeight;
  if (kind !== "heard") bumpBadge();
  return item;
}

function bumpBadge() {
  const card = $("card-conversation").getBoundingClientRect();
  if (card.bottom > 0 && card.top < window.innerHeight) return;
  ui.unreadConversation += 1;
  const badge = $("badge-conversation");
  badge.textContent = String(ui.unreadConversation);
  badge.hidden = false;
}

function toolText(ev) {
  const args = ev.arguments || {};
  const detail = args.question || args.text || args.query || "";
  return detail ? `${ev.name} — ${detail}` : ev.name;
}

function renderTranscriptEntry(ev) {
  switch (ev.type) {
    case "user": return addMessage("user", ev.text, ev.ts, { label: ev.source === "typed" ? "You (typed)" : "You" });
    case "reply": return finishReply(ev.text, ev.ts);
    case "heard": return addMessage("heard", ev.text, ev.ts);
    case "tool": return addMessage("tool", toolText(ev), ev.ts);
    case "seen": return addMessage("seen", `${ev.source}: ${ev.description}`, ev.ts);
    case "error": return addMessage("error", ev.message || "Something went wrong.", ev.ts);
    case "interrupted": return addMessage("interrupted", ev.reason === "voice" ? "Stopped by voice" : "Stopped", ev.ts);
    default: return null;
  }
}

function streamReply(text) {
  if (!ui.streamingReply) {
    ui.streamingReply = addMessage("reply", text);
    ui.streamingReply.classList.add("streaming");
  } else {
    ui.streamingReply.querySelector(".body").textContent = text;
    $("transcript").scrollTop = $("transcript").scrollHeight;
  }
}

function finishReply(text, ts) {
  if (ui.streamingReply) {
    ui.streamingReply.querySelector(".body").textContent = text;
    ui.streamingReply.classList.remove("streaming");
    ui.streamingReply = null;
  } else {
    addMessage("reply", text, ts);
  }
}

// ---------------------------------------------------------------- panels
function setStatus(state) {
  ui.state = state;
  $("stop-btn").classList.toggle("active", state === "speaking" || state === "thinking");
  const shown = ui.muted ? "muted" : state;
  const pill = $("state-pill");
  pill.dataset.state = shown;
  pill.textContent = shown;
}

function setMuted(muted) {
  ui.muted = muted;
  document.body.classList.toggle("muted", muted);
  const btn = $("mute-btn");
  btn.setAttribute("aria-pressed", String(muted));
  btn.textContent = muted ? "Unmute mic" : "Mute mic";
  setStatus(ui.state);
  renderPills();
}

function renderConfig(config) {
  ui.config = { ...ui.config, ...config };
  const c = ui.config;
  $("mic-name").textContent = c.mic || "—";
  $("brain-model").textContent = c.model || "—";
  $("vision-model").textContent = c.vision_model || "off";
  const chain = $("brain-chain");
  chain.replaceChildren(...[c.model, ...(c.fallbacks || [])].filter(Boolean).map((m) => el("li", "", m)));
  const select = $("model-select");
  if (c.model && select.value !== c.model) select.value = c.model;
  renderPills();
}

function renderModels(models) {
  const select = $("model-select");
  select.replaceChildren(...(models || []).map((m) => { const o = el("option", "", m); o.value = m; return o; }));
  if (ui.config.model) select.value = ui.config.model;
}

const HEALTH_LABELS = { echo: "ECHO proxy", ollama: "Ollama", vision: "Vision model", local_brain: "Local brain" };

function renderHealth(services) {
  const list = $("health");
  const rows = Object.entries(services || {}).map(([key, s]) => {
    const li = el("li");
    li.append(el("span", `dot ${s.ok ? "ok" : "down"}`), el("span", "", HEALTH_LABELS[key] || key), el("span", "detail", s.detail || ""));
    return li;
  });
  list.replaceChildren(...(rows.length ? rows : [el("li", "dim", "Checking…")]));
  ui.health = services || {};
  $("brand-dot").classList.toggle("ok", Boolean(ui.health.echo?.ok));
  renderPills();
}

function renderSeen(seen) {
  if (!seen) return;
  const img = $("vision-img");
  const empty = $("vision-empty");
  if (seen.image) {
    img.src = seen.image;
    img.alt = `Latest ${seen.source} capture`;
    img.hidden = false;
    empty.hidden = true;
  } else if (seen.error) {
    img.hidden = true;
    empty.hidden = false;
    empty.textContent = `Could not capture the ${seen.source}.`;
  }
  const desc = $("vision-desc");
  desc.classList.toggle("error", Boolean(seen.error));
  desc.replaceChildren(el("span", "src", seen.source), document.createTextNode(seen.description || ""));
}

function renderPills() {
  const pills = $("dock-pills");
  const pill = (dotClass, text) => { const p = el("span", "pill"); p.append(el("span", `dot ${dotClass}`), document.createTextNode(text)); return p; };
  pills.replaceChildren(
    pill(ui.muted ? "" : "ok", ui.muted ? "Mic muted" : "Mic live"),
    pill(ui.health.echo?.ok ? "ok" : "down", `Brain: ${ui.config.model || "—"}`),
    pill(ui.health.vision?.ok ? "ok" : "down", "Eyes"),
  );
}

// ---------------------------------------------------------------- memory
let memoryTimer = null;
async function loadMemory() {
  const q = $("memory-search").value.trim();
  const list = $("memory-list");
  try {
    const data = await api(`/api/memory?limit=100&q=${encodeURIComponent(q)}`);
    if (!data.enabled) {
      list.replaceChildren(el("li", "empty", "Memory is disabled (MEMORY_ENABLED=false)."));
      return;
    }
    $("memory-total").textContent = `${data.total} ${data.total === 1 ? "fact" : "facts"}`;
    const badge = $("badge-memory");
    badge.textContent = String(data.total);
    badge.hidden = data.total === 0;
    list.replaceChildren(...(data.items.length ? data.items.map((m) => {
      const li = el("li", "", m.text);
      const when = new Date(m.created_at);
      if (m.created_at && !Number.isNaN(when.getTime())) li.append(el("time", "", when.toLocaleString()));
      return li;
    }) : [el("li", "empty", q ? "No matching memories." : "No memories yet. Say “Hey JARVIS, remember …”.")]));
  } catch (err) {
    list.replaceChildren(el("li", "empty", `Could not load memory: ${err.message}`));
  }
}

// ---------------------------------------------------------------- orb + wave
const wave = $("wave");
const waveLevels = new Array(WAVE_BARS).fill(0);
wave.replaceChildren(...waveLevels.map(() => el("span")));

function pushWave(level) {
  waveLevels.shift();
  waveLevels.push(level);
  wave.setAttribute("aria-valuenow", String(Math.round(level * 100)));
  [...wave.children].forEach((bar, i) => { bar.style.transform = `scaleY(${Math.max(0.04, waveLevels[i])})`; });
}

const orb = $("orb");
const ctx = orb.getContext("2d");
const dpr = window.devicePixelRatio || 1;
orb.width = 220 * dpr; orb.height = 220 * dpr; ctx.scale(dpr, dpr);
let orbLevel = 0;
let orbSpin = 0;

function drawOrb() {
  const target = ui.muted ? 0 : Math.max(ui.micLevel, ui.botLevel * 1.2);
  orbLevel += (target - orbLevel) * 0.18;
  ui.micLevel *= 0.92; ui.botLevel *= 0.92;
  orbSpin += ui.state === "thinking" ? 0.06 : 0.008;
  const cx = 110, cy = 110, base = 52, r = base + orbLevel * 34;
  ctx.clearRect(0, 0, 220, 220);
  const speaking = ui.state === "speaking";
  const core = ui.muted ? "rgba(122,138,160,0.35)" : speaking ? "rgba(0,198,255,0.9)" : "rgba(0,242,254,0.75)";
  const halo = ctx.createRadialGradient(cx, cy, r * 0.2, cx, cy, r * 1.7);
  halo.addColorStop(0, ui.muted ? "rgba(122,138,160,0.18)" : "rgba(0,242,254,0.22)");
  halo.addColorStop(1, "rgba(0,242,254,0)");
  ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, r * 1.7, 0, Math.PI * 2); ctx.fill();
  const body = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.1, cx, cy, r);
  body.addColorStop(0, "rgba(232,237,242,0.9)"); body.addColorStop(0.35, core); body.addColorStop(1, "rgba(13,21,39,0.9)");
  ctx.fillStyle = body; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
  ctx.lineWidth = 2; ctx.strokeStyle = ui.muted ? "rgba(122,138,160,0.5)" : "rgba(0,242,254,0.8)";
  for (let k = 0; k < 3; k++) {
    const a = orbSpin * (k % 2 ? -1 : 1) + (k * Math.PI * 2) / 3;
    ctx.beginPath(); ctx.arc(cx, cy, r + 14 + k * 7, a, a + Math.PI * (ui.state === "thinking" ? 0.9 : 0.35)); ctx.stroke();
  }
  requestAnimationFrame(drawOrb);
}

// ---------------------------------------------------------------- events
function handle(ev) {
  switch (ev.type) {
    case "snapshot":
      $("transcript").replaceChildren();
      ui.streamingReply = null;
      setMuted(Boolean(ev.muted));
      renderModels(ev.models);
      renderConfig(ev.config || {});
      renderHealth(ev.health || {});
      setStatus(ev.status || "listening");
      (ev.transcript || []).forEach(renderTranscriptEntry);
      renderSeen(ev.last_seen);
      break;
    case "status": setStatus(ev.state); break;
    case "muted": setMuted(Boolean(ev.muted)); break;
    case "mic_level": ui.micLevel = Math.max(ui.micLevel, ev.level); pushWave(ev.level); break;
    case "bot_level": ui.botLevel = Math.max(ui.botLevel, ev.level); break;
    case "reply_chunk": streamReply(ev.text); break;
    case "config": renderConfig(ev.config || {}); break;
    case "health": renderHealth(ev.services); break;
    case "seen": renderSeen(ev); renderTranscriptEntry(ev); break;
    case "tool":
      renderTranscriptEntry(ev);
      if (ev.name === "remember") setTimeout(loadMemory, 1500);
      break;
    default: renderTranscriptEntry(ev);
  }
}

let retryMs = 500;
// A restarted JARVIS issues a new dashboard token; the old one is rejected
// forever. When a reconnect fails and the server answers 401, reload.
async function serverHasNewSession() {
  try {
    const res = await fetch("/api/state", { headers: { "X-JARVIS-Token": TOKEN }, cache: "no-store" });
    return res.status === 401;
  } catch { return false; }
}
function connect() {
  let opened = false;
  const ws = new WebSocket(`ws://${location.host}/ws?token=${encodeURIComponent(TOKEN)}`);
  ws.onopen = () => { opened = true; retryMs = 500; $("conn").textContent = "Live"; $("conn").classList.add("ok"); };
  ws.onmessage = (msg) => { try { handle(JSON.parse(msg.data)); } catch (err) { console.error(err); } };
  ws.onclose = async () => {
    $("conn").textContent = "Reconnecting…"; $("conn").classList.remove("ok");
    setStatus("offline");
    if (!opened && (await serverHasNewSession())) { $("conn").textContent = "JARVIS restarted, reloading"; setTimeout(() => location.reload(), 400); return; }
    setTimeout(connect, retryMs + Math.random() * retryMs * 0.3);
    retryMs = Math.min(RECONNECT_MAX_MS, retryMs * 2);
  };
}

// ---------------------------------------------------------------- controls
async function withButton(btn, fn) {
  btn.disabled = true;
  try { await fn(); } catch (err) { addMessage("error", err.message); } finally { btn.disabled = false; }
}

$("say-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("say-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  withButton(e.submitter || $("say-form").querySelector("button"), () => api("/api/say", { text }));
});
$("look-camera").addEventListener("click", (e) => withButton(e.currentTarget, () => api("/api/look", { source: "camera" })));
$("look-screen").addEventListener("click", (e) => withButton(e.currentTarget, () => api("/api/look", { source: "screen" })));
function stopSpeaking() {
  if (ui.streamingReply) { ui.streamingReply.classList.remove("streaming"); ui.streamingReply = null; }
  return api("/api/stop", {}).catch((err) => addMessage("error", err.message));
}
$("stop-btn").addEventListener("click", stopSpeaking);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !e.repeat) { e.preventDefault(); stopSpeaking(); }
});
$("mute-btn").addEventListener("click", (e) => withButton(e.currentTarget, () => api("/api/mute", { muted: !ui.muted })));
$("model-select").addEventListener("change", (e) => {
  const model = e.target.value;
  api("/api/model", { model }).catch((err) => { addMessage("error", err.message); e.target.value = ui.config.model || ""; });
});
$("clear-btn").addEventListener("click", () => { $("transcript").replaceChildren(); ui.streamingReply = null; });
$("show-ambient").addEventListener("change", (e) => $("transcript").classList.toggle("show-ambient", e.target.checked));
$("memory-search").addEventListener("input", () => { clearTimeout(memoryTimer); memoryTimer = setTimeout(loadMemory, 250); });

document.querySelectorAll(".nav-item[data-target]").forEach((a) => a.addEventListener("click", (e) => {
  e.preventDefault();
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n === a));
  $(a.dataset.target).scrollIntoView({ behavior: "smooth", block: "start" });
  if (a.dataset.target === "card-conversation") { ui.unreadConversation = 0; $("badge-conversation").hidden = true; }
}));

function tick() { $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
setInterval(tick, 1000); tick();
renderPills();
loadMemory();
connect();
requestAnimationFrame(drawOrb);
