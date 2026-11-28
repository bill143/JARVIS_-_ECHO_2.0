/* JARVIS home: live client for the sphere console. All text goes in via textContent. */
const TOKEN = document.querySelector('meta[name="jarvis-token"]').content;
const $ = (id) => document.getElementById(id);
const RECONNECT_BASE_MS = 500;
const RECONNECT_MAX_MS = 10000;
const STATE_LABELS = {
  starting: "Starting", listening: "Listening", thinking: "Thinking", speaking: "Speaking",
  muted: "Mic muted", offline: "Offline",
};
const LABELS = { user: "You", reply: "JARVIS", tool: "Tool", seen: "Saw", error: "Error", interrupted: "Stopped" };
const HEALTH_LABELS = { echo: "ECHO proxy", ollama: "Ollama", vision: "Vision model", local_brain: "Local brain" };

const ui = { state: "starting", muted: false, live: false, config: {}, streaming: null, lastUser: "", lastReply: "" };
const sphere = window.JarvisSphere ? window.JarvisSphere.create($("sphere")) : null;

// ------------------------------------------------------------------ helpers
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

class AuthExpired extends Error {}

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-JARVIS-Token": TOKEN, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) throw new AuthExpired("JARVIS restarted");
  const json = await res.json().catch(() => ({ success: false, error: { message: `HTTP ${res.status}` } }));
  if (!json.success) throw new Error(json.error?.message || `HTTP ${res.status}`);
  return json.data;
}

function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

// ------------------------------------------------------------------ clock
function tick() {
  const now = new Date();
  $("clock").textContent = now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });
  $("clock").dateTime = now.toISOString();
  $("date").textContent = now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

// ------------------------------------------------------------------ state
function shownState() {
  if (!ui.live) return "offline";
  return ui.muted && ui.state === "listening" ? "muted" : ui.state;
}

function renderState() {
  const shown = shownState();
  document.body.dataset.state = shown;
  $("state-label").textContent = STATE_LABELS[shown] || shown;
  $("mc-state").textContent = STATE_LABELS[shown] || shown;
  $("stop").hidden = !(ui.live && (ui.state === "speaking" || ui.state === "thinking"));
  if (sphere) sphere.setState(shown);
}

function setConnection(live, label) {
  ui.live = live;
  document.body.classList.toggle("live", live);
  document.body.classList.toggle("offline", !live && label !== "Connecting");
  $("conn-label").textContent = label;
  $("mc-conn").textContent = label;
  renderState();
}

function setMuted(muted) {
  ui.muted = muted;
  const btn = $("tb-mic");
  btn.setAttribute("aria-pressed", String(muted));
  btn.setAttribute("aria-label", muted ? "Unmute microphone" : "Mute microphone");
  btn.title = muted ? "Unmute microphone" : "Mute microphone";
  renderState();
}

// ------------------------------------------------------------------ transcript + caption
function addMessage(kind, text, ts, label) {
  const list = $("transcript");
  const item = el("li", `msg ${kind}`);
  const meta = el("div", "meta");
  meta.append(el("span", "", label || LABELS[kind] || kind), el("time", "", fmtTime(ts || Date.now() / 1000)));
  item.append(meta, el("div", "body", text));
  list.append(item);
  while (list.children.length > 300) list.firstElementChild.remove();
  list.scrollTop = list.scrollHeight;
  return item;
}

function setCaption(user, reply) {
  if (user !== undefined) ui.lastUser = user;
  if (reply !== undefined) ui.lastReply = reply;
  $("cap-user").textContent = ui.lastUser;
  $("cap-user").hidden = !ui.lastUser;
  $("cap-reply").textContent = ui.lastReply;
  $("caption").hidden = !(ui.lastUser || ui.lastReply) || !$("chat").hidden;
}

function toolText(ev) {
  const args = ev.arguments || {};
  const detail = args.question || args.text || args.query || "";
  return detail ? `${ev.name}: ${detail}` : ev.name;
}

function streamReply(text) {
  if (!ui.streaming) ui.streaming = addMessage("reply", text);
  else ui.streaming.querySelector(".body").textContent = text;
  setCaption(undefined, text);
}

function finishReply(text, ts) {
  if (ui.streaming) {
    ui.streaming.querySelector(".body").textContent = text;
    ui.streaming = null;
  } else {
    addMessage("reply", text, ts);
  }
  setCaption(undefined, text);
}

function renderEntry(ev) {
  switch (ev.type) {
    case "user":
      addMessage("user", ev.text, ev.ts, ev.source === "typed" ? "You (typed)" : "You");
      setCaption(ev.text, "");
      break;
    case "reply": finishReply(ev.text, ev.ts); break;
    case "tool": addMessage("tool", toolText(ev), ev.ts); break;
    case "seen": addMessage("seen", `${ev.source}: ${ev.description}`, ev.ts); break;
    case "error": addMessage("error", ev.message || "Something went wrong.", ev.ts); break;
    case "interrupted": addMessage("interrupted", ev.reason === "voice" ? "Stopped by voice" : "Stopped", ev.ts); break;
    default: break;
  }
}

// ------------------------------------------------------------------ Mission Control content
function renderConfig(config) {
  ui.config = { ...ui.config, ...config };
  const c = ui.config;
  $("mc-mic").textContent = c.mic || "—";
  $("vision-model").textContent = c.vision_model || "off";
  $("brain-chain").replaceChildren(...[c.model, ...(c.fallbacks || [])].filter(Boolean).map((m) => el("li", "", m)));
  const select = $("model-select");
  if (c.model && select.value !== c.model) select.value = c.model;
  const eyes = Boolean(c.vision_model);
  $("tb-camera").disabled = !eyes;
  $("tb-screen").disabled = !eyes;
}

function renderModels(models) {
  const select = $("model-select");
  select.replaceChildren(...(models || []).map((m) => { const o = el("option", "", m); o.value = m; return o; }));
  if (ui.config.model) select.value = ui.config.model;
}

function renderHealth(services) {
  const rows = Object.entries(services || {}).map(([key, s]) => {
    const li = el("li");
    li.append(el("span", `dot ${s.ok ? "ok" : ""}`), el("span", "", HEALTH_LABELS[key] || key), el("span", "detail", s.detail || ""));
    return li;
  });
  $("health").replaceChildren(...(rows.length ? rows : [el("li", "dim", "Checking…")]));
}

function renderSeen(seen) {
  if (!seen) return;
  const img = $("seen-img");
  if (seen.image) {
    img.src = seen.image;
    img.alt = `Latest ${seen.source} capture`;
    img.hidden = false;
    $("seen-empty").hidden = true;
  } else if (seen.error) {
    img.hidden = true;
    $("seen-empty").hidden = false;
    $("seen-empty").textContent = `Could not capture the ${seen.source}.`;
  }
  const desc = $("seen-desc");
  desc.classList.toggle("error", Boolean(seen.error));
  desc.textContent = seen.description ? `${seen.source}: ${seen.description}` : "";
}

let memoryTimer = null;
async function loadMemory() {
  const q = $("memory-search").value.trim();
  const list = $("memory-list");
  try {
    const data = await api(`/api/memory?limit=50&q=${encodeURIComponent(q)}`);
    if (!data.enabled) {
      list.replaceChildren(el("li", "dim", "Memory is off (MEMORY_ENABLED=false)."));
      $("memory-total").textContent = "";
      return;
    }
    $("memory-total").textContent = `· ${data.total} ${data.total === 1 ? "fact" : "facts"}`;
    list.replaceChildren(...(data.items.length ? data.items.map((m) => {
      const li = el("li", "", m.text);
      const when = new Date(m.created_at);
      if (m.created_at && !Number.isNaN(when.getTime())) li.append(el("time", "", when.toLocaleString()));
      return li;
    }) : [el("li", "dim", q ? "No matching memories." : "No memories yet.")]));
  } catch (err) {
    if (err instanceof AuthExpired) { reloadForNewSession(); return; }
    list.replaceChildren(el("li", "dim", `Could not load memory: ${err.message}`));
  }
}

// ------------------------------------------------------------------ events
function handle(ev) {
  switch (ev.type) {
    case "snapshot":
      $("transcript").replaceChildren();
      ui.streaming = null;
      setMuted(Boolean(ev.muted));
      renderModels(ev.models);
      renderConfig(ev.config || {});
      renderHealth(ev.health || {});
      ui.state = ev.status || "listening";
      (ev.transcript || []).forEach(renderEntry);
      renderSeen(ev.last_seen);
      renderState();
      break;
    case "status": ui.state = ev.state; renderState(); break;
    case "muted": setMuted(Boolean(ev.muted)); break;
    case "mic_level": if (sphere && ui.state !== "speaking" && !ui.muted) sphere.setLevel(ev.level); break;
    case "bot_level": if (sphere) sphere.setLevel(ev.level); break;
    case "reply_chunk": streamReply(ev.text); break;
    case "config": renderConfig(ev.config || {}); break;
    case "health": renderHealth(ev.services); break;
    case "seen": renderSeen(ev); renderEntry(ev); break;
    case "tool":
      renderEntry(ev);
      if (ev.name === "remember") setTimeout(loadMemory, 1500);
      break;
    default: renderEntry(ev);
  }
}

// ------------------------------------------------------------------ connection (auto-reconnect)
// JARVIS issues a fresh dashboard token every launch. After a restart the old
// page's token is rejected forever, which is what left the console stuck on
// "Reconnecting…". So when a reconnect fails, ask the server whether it is up
// with a new session; if so, reload to pick up the new token.
let retryMs = RECONNECT_BASE_MS;
let reloading = false;

function reloadForNewSession() {
  if (reloading) return;
  reloading = true;
  setConnection(false, "JARVIS restarted, reloading");
  setTimeout(() => window.location.reload(), 400);
}

async function serverHasNewSession() {
  try {
    const res = await fetch("/api/state", { headers: { "X-JARVIS-Token": TOKEN }, cache: "no-store" });
    return res.status === 401;
  } catch {
    return false;  // server down: keep backing off
  }
}

function scheduleReconnect() {
  const wait = Math.round(retryMs + Math.random() * retryMs * 0.3);
  setConnection(false, `Offline, retrying in ${Math.ceil(wait / 1000)}s`);
  setTimeout(connect, wait);
  retryMs = Math.min(RECONNECT_MAX_MS, retryMs * 2);
}

function connect() {
  if (reloading) return;
  let opened = false;
  const ws = new WebSocket(`ws://${location.host}/ws?token=${encodeURIComponent(TOKEN)}`);
  ws.onopen = () => {
    opened = true;
    retryMs = RECONNECT_BASE_MS;
    setConnection(true, "Live");
    loadMemory();
  };
  ws.onmessage = (msg) => {
    try { handle(JSON.parse(msg.data)); } catch (err) { console.error("bad dashboard event", err); }
  };
  ws.onclose = async () => {
    if (reloading) return;
    if (!opened && (await serverHasNewSession())) { reloadForNewSession(); return; }
    scheduleReconnect();
  };
}

window.addEventListener("online", () => { retryMs = RECONNECT_BASE_MS; });

// ------------------------------------------------------------------ controls
async function run(btn, fn) {
  if (btn) btn.disabled = true;
  try {
    await fn();
  } catch (err) {
    if (err instanceof AuthExpired) { reloadForNewSession(); return; }
    addMessage("error", err.message);
    openChat(true);
  } finally {
    if (btn) btn.disabled = false;
    renderConfig({});
  }
}

function stopSpeaking() {
  ui.streaming = null;
  return run(null, () => api("/api/stop", {}));
}

function openChat(open) {
  $("chat").hidden = !open;
  $("tb-chat").setAttribute("aria-pressed", String(open));
  setCaption();
  if (open) $("say-input").focus();
}

function openMission(open) {
  $("mc").hidden = !open;
  $("mc-pill").setAttribute("aria-expanded", String(open));
  if (open) { loadMemory(); $("mc-close").focus(); } else { $("mc-pill").focus(); }
}

$("tb-mic").addEventListener("click", (e) => run(e.currentTarget, () => api("/api/mute", { muted: !ui.muted })));
$("tb-screen").addEventListener("click", (e) => run(e.currentTarget, () => api("/api/look", { source: "screen" })));
$("tb-camera").addEventListener("click", (e) => run(e.currentTarget, () => api("/api/look", { source: "camera" })));
$("tb-chat").addEventListener("click", () => openChat($("chat").hidden));
$("chat-close").addEventListener("click", () => openChat(false));
$("mc-pill").addEventListener("click", () => openMission($("mc").hidden));
$("mc-close").addEventListener("click", () => openMission(false));
$("stop").addEventListener("click", stopSpeaking);
$("say-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("say-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  run(e.submitter, () => api("/api/say", { text }));
});
$("model-select").addEventListener("change", (e) => {
  const model = e.target.value;
  api("/api/model", { model }).catch((err) => {
    if (err instanceof AuthExpired) { reloadForNewSession(); return; }
    addMessage("error", err.message);
    e.target.value = ui.config.model || "";
  });
});
$("memory-search").addEventListener("input", () => { clearTimeout(memoryTimer); memoryTimer = setTimeout(loadMemory, 250); });

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !e.repeat) {
    // Esc always stops him; it also closes an open panel.
    e.preventDefault();
    stopSpeaking();
    if (!$("mc").hidden) openMission(false);
    else if (!$("chat").hidden) openChat(false);
    return;
  }
  const key = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (key === "m" || key === "k")) {
    e.preventDefault();
    openMission($("mc").hidden);
  }
});

tick();
setInterval(tick, 1000);
renderState();
connect();
