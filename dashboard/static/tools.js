/* JARVIS Skills & Tools page. All text rendered with textContent; secret values are never displayed. */
"use strict";

const TOKEN = document.querySelector('meta[name="jarvis-token"]').content;
const $ = (id) => document.getElementById(id);

async function api(path, { method = "GET", body, form } = {}) {
  const headers = { "X-JARVIS-Token": TOKEN };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: form || (body === undefined ? undefined : JSON.stringify(body)) });
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

function btn(label, className, onClick) {
  const b = el("button", `btn ${className || ""}`.trim(), label);
  b.type = "button";
  b.addEventListener("click", onClick);
  return b;
}

function toggle(checked, label, onChange) {
  const s = el("button", "switch");
  s.type = "button";
  s.setAttribute("role", "switch");
  s.setAttribute("aria-checked", String(checked));
  s.setAttribute("aria-label", label);
  s.addEventListener("click", async () => {
    s.disabled = true;
    try { await onChange(s.getAttribute("aria-checked") !== "true"); } catch (err) { alert(err.message); }
    load();
  });
  return s;
}

const STATE = { connected: ["ok", "Connected"], connecting: ["", "Connecting…"], error: ["down", "Not connected"], off: ["", "Off"] };

function serverCard(s) {
  const card = el("article", "server");
  const head = el("div", "server-head");
  const [dotClass, stateLabel] = STATE[s.status.state] || ["", s.status.state];
  head.append(el("span", `dot ${dotClass}`), el("span", "name", s.name), el("span", "chip", stateLabel),
    el("span", "chip", s.transport), el("span", "target", s.target), el("span", "spacer"),
    toggle(s.enabled, `${s.name} on/off`, (on) => api(`/api/toolbox/servers/${s.id}`, { method: "PUT", body: { enabled: on } })));
  card.append(head);
  if (s.status.error) card.append(el("p", "server-error", s.status.error));
  if (s.missing_secrets.length) card.append(el("p", "server-missing", `Needs secret(s): ${s.missing_secrets.join(", ")} (add them under Secrets).`));
  if (s.tools.length) {
    const chips = el("div", "tool-chips");
    s.tools.forEach((t) => {
      const chip = el("button", `tool-chip ${t.enabled ? "" : "off"}`, t.name);
      chip.type = "button";
      chip.title = `${t.description || t.name}\n\nClick to switch ${t.enabled ? "off" : "on"}.`;
      chip.setAttribute("aria-pressed", String(t.enabled));
      chip.addEventListener("click", async () => {
        try { await api(`/api/toolbox/tools/${encodeURIComponent(t.name)}`, { method: "PUT", body: { enabled: !t.enabled } }); } catch (err) { alert(err.message); }
        load();
      });
      chips.append(chip);
    });
    card.append(chips);
  }
  const result = el("p", "test-result");
  const actions = el("div", "row-btns");
  actions.append(
    btn("Test connection", "small", async () => {
      result.className = "test-result"; result.textContent = "Testing…";
      try {
        const r = await api(`/api/toolbox/servers/${s.id}/test`, { method: "POST", body: {} });
        result.className = `test-result ${r.ok ? "ok" : "bad"}`;
        result.textContent = r.ok ? `OK: ${r.tools.length} tool(s): ${r.tools.map((t) => t.name).join(", ")}` : `Failed: ${r.error}`;
      } catch (err) { result.className = "test-result bad"; result.textContent = err.message; }
    }),
    btn("Remove", "small danger", async () => {
      if (!confirm(`Remove ${s.name}? JARVIS will lose its tools.`)) return;
      try { await api(`/api/toolbox/servers/${s.id}`, { method: "DELETE" }); } catch (err) { alert(err.message); }
      load();
    }),
  );
  card.append(actions, result);
  return card;
}

function catalogItem(c) {
  const box = el("div", "catalog-item");
  box.append(el("div", "name", c.name), el("p", "hint", c.about));
  if (c.needs.length) {
    const needs = el("ul", "needs");
    c.needs.forEach((n) => needs.append(el("li", "", n)));
    box.append(needs);
  }
  box.append(c.added ? el("span", "chip ok", "Added") : btn("Add", "small primary", async (e) => {
    e.currentTarget.disabled = true;
    try { await api(`/api/toolbox/presets/${c.id}`, { method: "POST", body: {} }); } catch (err) { alert(err.message); }
    load();
  }));
  return box;
}

function row(titleText, desc, control, extra) {
  const li = el("li", "tool-row");
  const text = el("div");
  text.append(el("div", "title", titleText));
  if (desc) text.append(el("div", "desc", desc));
  li.append(control, text, extra || el("span"));
  return li;
}

async function load() {
  let data;
  try { data = await api("/api/toolbox"); }
  catch (err) { $("server-list").replaceChildren(el("p", "empty", `Could not load tools: ${err.message}`)); return; }
  $("active-count").textContent = `${data.active_tool_count} active tools`;
  $("server-list").replaceChildren(...(data.servers.length ? data.servers.map(serverCard)
    : [el("p", "empty", "No tool servers yet. Add one, or pick a one-click tool below.")]));
  $("catalog").replaceChildren(...data.catalog.map(catalogItem));
  $("builtin-list").replaceChildren(...data.builtin.map((t) => row(`${t.name}`, `${t.group} · ${t.description}`,
    toggle(t.enabled, `${t.name} on/off`, (on) => api(`/api/toolbox/tools/${encodeURIComponent(t.name)}`, { method: "PUT", body: { enabled: on } })))));
  $("skill-list").replaceChildren(...(data.skills.length ? data.skills.map((s) => row(s.name, s.description,
    toggle(s.enabled, `${s.name} on/off`, (on) => api(`/api/toolbox/skills/${encodeURIComponent(s.name)}`, { method: "PUT", body: { enabled: on } })),
    btn("Remove", "small danger", async () => {
      if (!confirm(`Remove skill ${s.name}?`)) return;
      try { await api(`/api/toolbox/skills/${encodeURIComponent(s.name)}`, { method: "DELETE" }); } catch (err) { alert(err.message); }
      load();
    }))) : [el("li", "empty", "No skills yet. Import a SKILL.md file or a .zip of skill folders.")]));
  $("secret-list").replaceChildren(...(data.secrets.length ? data.secrets.map((name) => row(name, "set · value hidden",
    el("span", "dot ok"), btn("Delete", "small danger", async () => {
      if (!confirm(`Delete secret ${name}?`)) return;
      try { await api(`/api/toolbox/secrets/${encodeURIComponent(name)}`, { method: "DELETE" }); } catch (err) { alert(err.message); }
      load();
    }))) : [el("li", "empty", "No secrets saved.")]));
}

// ---- add server modal
const form = $("server-form");
function syncTransport() {
  const stdio = form.elements.transport.value === "stdio";
  form.querySelectorAll(".stdio-only").forEach((n) => { n.hidden = !stdio; });
  form.querySelectorAll(".url-only").forEach((n) => { n.hidden = stdio; });
}
form.elements.transport.addEventListener("change", syncTransport);
function openModal() { form.reset(); syncTransport(); $("form-error").textContent = ""; $("modal").hidden = false; form.elements.name.focus(); }
function closeModal() { $("modal").hidden = true; }
$("add-server").addEventListener("click", openModal);
$("modal-close").addEventListener("click", closeModal);
$("modal-cancel").addEventListener("click", closeModal);
$("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("modal").hidden) closeModal(); });
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = form.elements;
  const body = {
    name: f.name.value.trim(), transport: f.transport.value, command: f.command.value.trim(),
    args: f.args.value.split("\n").map((s) => s.trim()).filter(Boolean), url: f.url.value.trim(),
    secret_env: f.secret_env.value.split(",").map((s) => s.trim()).filter(Boolean), auth_secret: f.auth_secret.value.trim(),
  };
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true; $("form-error").textContent = "Connecting…";
  try { await api("/api/toolbox/servers", { method: "POST", body }); closeModal(); load(); }
  catch (err) { $("form-error").textContent = err.message; }
  finally { submit.disabled = false; }
});

// ---- skills + secrets
$("skill-input").addEventListener("change", async (e) => {
  const files = [...e.target.files];
  e.target.value = "";
  if (!files.length) return;
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  $("skill-status").textContent = "Importing…";
  try {
    const r = await api("/api/toolbox/skills", { method: "POST", form: fd });
    $("skill-status").textContent = [r.imported.length ? `Imported: ${r.imported.join(", ")}.` : "Nothing imported.", ...r.problems].join(" ");
  } catch (err) { $("skill-status").textContent = err.message; }
  load();
});
$("secret-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("secret-name"); const value = $("secret-value");
  try { await api("/api/toolbox/secrets", { method: "POST", body: { name: name.value.trim(), value: value.value } }); name.value = ""; }
  catch (err) { alert(err.message); }
  finally { value.value = ""; }
  load();
});

load();
