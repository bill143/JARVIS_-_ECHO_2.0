/* JARVIS Memory page: Facts + People. All text rendered with textContent. */
"use strict";

const TOKEN = document.querySelector('meta[name="jarvis-token"]').content;
const $ = (id) => document.getElementById(id);
const FIELDS = ["name", "relationship", "company", "role", "phone", "email", "notes"];
const photoUrls = new Map(); // photo id -> blob URL (photos need the token header)

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

function btn(label, className, onClick, aria) {
  const b = el("button", `btn ${className || ""}`.trim(), label);
  b.type = "button";
  if (aria) b.setAttribute("aria-label", aria);
  b.addEventListener("click", onClick);
  return b;
}

function when(iso) {
  const d = new Date(iso);
  return iso && !Number.isNaN(d.getTime()) ? d.toLocaleString() : "";
}

async function photoUrl(personId, photoId) {
  if (photoUrls.has(photoId)) return photoUrls.get(photoId);
  const res = await fetch(`/api/people/${personId}/photos/${photoId}`, { headers: { "X-JARVIS-Token": TOKEN } });
  if (!res.ok) throw new Error(`photo HTTP ${res.status}`);
  const url = URL.createObjectURL(await res.blob());
  photoUrls.set(photoId, url);
  return url;
}

// ---------------------------------------------------------------- tabs
function showTab(name) {
  for (const t of ["facts", "people"]) {
    const on = t === name;
    $(`tab-${t}`).classList.toggle("active", on);
    $(`tab-${t}`).setAttribute("aria-selected", String(on));
    $(`panel-${t}`).hidden = !on;
  }
  history.replaceState(null, "", name === "people" ? "#people" : "#facts");
}
$("tab-facts").addEventListener("click", () => showTab("facts"));
$("tab-people").addEventListener("click", () => showTab("people"));

// ---------------------------------------------------------------- facts
let factTimer = null;
async function loadFacts() {
  const list = $("fact-list");
  const q = $("fact-search").value.trim();
  try {
    const data = await api(`/api/memory?limit=200&q=${encodeURIComponent(q)}`);
    if (!data.enabled) { list.replaceChildren(el("li", "empty", "Memory is disabled (MEMORY_ENABLED=false).")); return; }
    $("count-facts").textContent = String(data.total);
    list.replaceChildren(...(data.items.length ? data.items.map(factRow)
      : [el("li", "empty", q ? "No matching facts." : "No facts yet. Add one above, or say “Hey JARVIS, remember …”.")]));
  } catch (err) {
    list.replaceChildren(el("li", "empty", `Could not load facts: ${err.message}`));
  }
  updateTotal();
}

function factRow(fact) {
  const li = el("li", "fact");
  const body = el("div");
  body.append(el("div", "", fact.text));
  const stamp = when(fact.created_at);
  if (stamp) body.append(el("time", "", stamp));
  const actions = el("div", "actions");
  actions.append(
    btn("Edit", "small", () => editFact(li, fact)),
    btn("Delete", "small danger", async () => {
      if (!confirm(`Delete this fact?\n\n${fact.text}`)) return;
      try { await api(`/api/memory/${fact.id}`, { method: "DELETE" }); loadFacts(); } catch (err) { alert(err.message); }
    }),
  );
  li.append(body, actions);
  return li;
}

function editFact(li, fact) {
  const area = el("textarea");
  area.value = fact.text; area.rows = 2; area.maxLength = 2000;
  const actions = el("div", "actions");
  actions.append(
    btn("Save", "small primary", async () => {
      const text = area.value.trim();
      if (!text) return;
      try { await api(`/api/memory/${fact.id}`, { method: "PUT", body: { text } }); loadFacts(); } catch (err) { alert(err.message); }
    }),
    btn("Cancel", "small", loadFacts),
  );
  li.replaceChildren(area, actions);
  area.focus();
}

$("fact-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("fact-input");
  const text = input.value.trim();
  if (!text) return;
  try { await api("/api/memory", { method: "POST", body: { text } }); input.value = ""; loadFacts(); }
  catch (err) { alert(err.message); }
});
$("fact-search").addEventListener("input", () => { clearTimeout(factTimer); factTimer = setTimeout(loadFacts, 250); });

// ---------------------------------------------------------------- people
let peopleTimer = null;
let editing = null; // person being edited (null = new)
let groups = [];      // [{id, name, count}]
let activeGroup = ""; // "" = All
let selecting = false;
const selected = new Set();
let shown = [];       // people currently listed

async function loadPeople() {
  const grid = $("people-grid");
  const q = $("people-search").value.trim();
  try {
    const all = await api(`/api/people?q=${encodeURIComponent(q)}`);
    groups = all.groups || [];
    if (activeGroup && !groups.some((g) => g.id === activeGroup)) activeGroup = "";
    const data = activeGroup
      ? await api(`/api/people?q=${encodeURIComponent(q)}&group=${encodeURIComponent(activeGroup)}`)
      : all;
    if (!q) $("count-people").textContent = String(all.total);
    renderGroupBar(all.total);
    shown = data.items;
    const groupName = groups.find((g) => g.id === activeGroup)?.name;
    let empty = q ? "No matching people." : "No people yet. Add someone with “+ New person”.";
    if (groupName) empty = q ? `Nobody in ${groupName} matches.` : `Nobody in ${groupName} yet.`;
    grid.replaceChildren(...(data.items.length ? data.items.map(personCard) : [el("div", "empty", empty)]));
  } catch (err) {
    grid.replaceChildren(el("div", "empty", `Could not load people: ${err.message}`));
  }
  renderBulkBar();
  updateTotal();
}

// ---------------------------------------------------------------- groups
function renderGroupBar(totalShown) {
  const chip = (id, name, count) => {
    const b = el("button", "group-chip");
    b.type = "button";
    b.setAttribute("aria-pressed", String(activeGroup === id));
    b.append(el("span", "", name), el("span", "n", String(count)));
    b.addEventListener("click", () => { activeGroup = id; loadPeople(); });
    return b;
  };
  $("group-chips").replaceChildren(chip("", "All", totalShown), ...groups.map((g) => chip(g.id, g.name, g.count)));
  $("group-rename").hidden = !activeGroup;
  $("group-delete").hidden = !activeGroup;
  const pick = $("bulk-group");
  const keep = pick.value;
  pick.replaceChildren(...groups.map((g) => { const o = el("option", "", g.name); o.value = g.id; return o; }));
  if (groups.some((g) => g.id === keep)) pick.value = keep;
  else if (activeGroup) pick.value = activeGroup;
}

$("group-new").addEventListener("click", async () => {
  const name = (prompt("Name of the new group (for example Clients or Golf):") || "").trim();
  if (!name) return;
  try {
    const g = await api("/api/people/groups", { method: "POST", body: { name } });
    activeGroup = g.id;
    loadPeople();
  } catch (err) { alert(err.message); }
});
$("group-rename").addEventListener("click", async () => {
  const g = groups.find((x) => x.id === activeGroup);
  if (!g) return;
  const name = (prompt(`Rename the group ${g.name} to:`, g.name) || "").trim();
  if (!name || name === g.name) return;
  try { await api(`/api/people/groups/${g.id}`, { method: "PUT", body: { name } }); loadPeople(); }
  catch (err) { alert(err.message); }
});
$("group-delete").addEventListener("click", async () => {
  const g = groups.find((x) => x.id === activeGroup);
  if (!g) return;
  if (!confirm(`Delete the group ${g.name}? The ${g.count} people in it are kept; they just leave this group.`)) return;
  try { await api(`/api/people/groups/${g.id}`, { method: "DELETE" }); activeGroup = ""; loadPeople(); }
  catch (err) { alert(err.message); }
});

// ---------------------------------------------------------------- bulk select
function renderBulkBar() {
  $("bulk-bar").hidden = !selecting;
  $("select-toggle").setAttribute("aria-pressed", String(selecting));
  $("select-toggle").textContent = selecting ? "Done selecting" : "Select people";
  $("bulk-count").textContent = `${selected.size} selected`;
  $("bulk-add").disabled = !selected.size || !groups.length;
}
$("select-toggle").addEventListener("click", () => { selecting = !selecting; selected.clear(); loadPeople(); });
$("bulk-clear").addEventListener("click", () => { selected.clear(); loadPeople(); });
$("bulk-all").addEventListener("click", () => { shown.forEach((p) => selected.add(p.id)); loadPeople(); });
$("bulk-add").addEventListener("click", async () => {
  const gid = $("bulk-group").value;
  const g = groups.find((x) => x.id === gid);
  if (!g || !selected.size) return;
  try {
    const r = await api(`/api/people/groups/${gid}/members`, { method: "POST", body: { person_ids: [...selected] } });
    $("recognize-result").textContent = `Added ${r.added} ${r.added === 1 ? "person" : "people"} to ${g.name}.`;
    selected.clear();
    loadPeople();
  } catch (err) { alert(err.message); }
});

function personCard(p) {
  const card = el("button", "person");
  card.type = "button";
  card.setAttribute("aria-label", `Edit ${p.name}`);
  const avatar = el("div", "avatar", (p.name || "?").trim().charAt(0).toUpperCase());
  if (p.photos.length) {
    photoUrl(p.id, p.photos[0].id).then((url) => {
      const img = el("img", "avatar"); img.src = url; img.alt = ""; avatar.replaceWith(img);
    }).catch(() => {});
  }
  const info = el("div");
  info.append(el("div", "name", p.name));
  const sub = [p.relationship, [p.role, p.company && `at ${p.company}`].filter(Boolean).join(" ")].filter(Boolean).join(" · ");
  if (sub) info.append(el("div", "meta", sub));
  const contact = [p.phone, p.email].filter(Boolean).join(" · ");
  if (contact) info.append(el("div", "meta", contact));
  const chips = el("div", "chips");
  const faces = p.photos.filter((ph) => ph.has_face).length;
  chips.append(el("span", `chip ${faces ? "ok" : "warn"}`, faces ? `${faces} face${faces === 1 ? "" : "s"} enrolled` : "no face photo"));
  if (p.facts.length) chips.append(el("span", "chip", `${p.facts.length} fact${p.facts.length === 1 ? "" : "s"}`));
  for (const gid of p.groups || []) {
    const g = groups.find((x) => x.id === gid);
    if (g) chips.append(el("span", "chip group", g.name));
  }
  info.append(chips);
  card.append(avatar, info);
  if (!selecting) {
    card.addEventListener("click", () => openEditor(p));
    return card;
  }
  const isOn = () => selected.has(p.id);
  card.classList.add("selectable");
  card.setAttribute("aria-label", `Select ${p.name}`);
  const box = el("input", "pick");
  box.type = "checkbox"; box.tabIndex = -1; box.setAttribute("aria-hidden", "true");
  const paint = () => {
    card.classList.toggle("selected", isOn());
    card.setAttribute("aria-pressed", String(isOn()));
    box.checked = isOn();
  };
  card.append(box);
  paint();
  card.addEventListener("click", () => {
    if (isOn()) selected.delete(p.id); else selected.add(p.id);
    paint();
    renderBulkBar();
  });
  return card;
}

function updateTotal() {
  const total = Number($("count-facts").textContent || 0) + Number($("count-people").textContent || 0);
  $("badge-total").textContent = String(total);
  $("badge-total").hidden = total === 0;
}

// ---------------------------------------------------------------- editor modal
const form = $("person-form");

function openEditor(person) {
  editing = person || null;
  form.reset();
  $("form-error").textContent = "";
  $("photo-status").textContent = "";
  $("modal-title").textContent = person ? `Edit ${person.name}` : "New person";
  $("delete-person").hidden = !person;
  for (const f of FIELDS) form.elements[f].value = person ? person[f] || "" : "";
  form.elements.facts.value = person ? person.facts.join("\n") : "";
  renderGroupPick(person ? person.groups || [] : (activeGroup ? [activeGroup] : []));
  renderPhotos();
  $("modal").hidden = false;
  form.elements.name.focus();
}

function renderGroupPick(memberOf) {
  const box = $("group-pick");
  if (!groups.length) { box.replaceChildren(el("span", "dim", "No groups yet. Use “+ New group”.")); return; }
  box.replaceChildren(...groups.map((g) => {
    const label = el("label");
    const cb = el("input");
    cb.type = "checkbox"; cb.value = g.id; cb.checked = memberOf.includes(g.id);
    label.append(cb, document.createTextNode(g.name));
    return label;
  }));
}

function closeEditor() { $("modal").hidden = true; editing = null; loadPeople(); }

function renderPhotos() {
  const strip = $("photo-strip");
  const dropzone = $("dropzone");
  if (!editing) {
    strip.replaceChildren(el("p", "hint", "Save the person first, then add photos."));
    dropzone.classList.add("disabled");
    return;
  }
  dropzone.classList.remove("disabled");
  strip.replaceChildren(...editing.photos.map((ph) => {
    const box = el("div", "thumb");
    const img = el("img"); img.alt = `${editing.name} photo`;
    photoUrl(editing.id, ph.id).then((url) => { img.src = url; }).catch(() => {});
    box.append(img, el("span", `flag ${ph.has_face ? "ok" : "warn"}`, ph.has_face ? "face" : "no face"),
      btn("✕", "remove", async () => {
        try {
          await api(`/api/people/${editing.id}/photos/${ph.id}`, { method: "DELETE" });
          editing = await api(`/api/people/${editing.id}`);
          renderPhotos();
        } catch (err) { $("photo-status").textContent = err.message; }
      }, "Remove photo"));
    return box;
  }));
}

async function uploadPhotos(files) {
  if (!editing || !files.length) return;
  const fd = new FormData();
  [...files].slice(0, 12).forEach((f) => fd.append("files", f, f.name));
  $("photo-status").textContent = `Uploading ${Math.min(files.length, 12)} photo(s) and finding faces…`;
  try {
    const data = await api(`/api/people/${editing.id}/photos`, { method: "POST", form: fd });
    editing = data.person;
    renderPhotos();
    const bad = data.results.filter((r) => !r.ok);
    const noFace = data.results.filter((r) => r.ok && !r.has_face);
    $("photo-status").textContent = [
      `${data.results.length - bad.length} added.`,
      noFace.length ? `${noFace.length} without a detectable face (won't help recognition).` : "",
      ...bad.map((r) => r.error),
    ].filter(Boolean).join(" ");
  } catch (err) { $("photo-status").textContent = err.message; }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(FIELDS.map((f) => [f, form.elements[f].value.trim()]));
  body.facts = form.elements.facts.value.split("\n").map((s) => s.trim()).filter(Boolean);
  body.groups = [...$("group-pick").querySelectorAll("input:checked")].map((i) => i.value);
  try {
    const wasNew = !editing;
    editing = wasNew ? await api("/api/people", { method: "POST", body })
                     : await api(`/api/people/${editing.id}`, { method: "PUT", body });
    if (wasNew) {
      $("modal-title").textContent = `Edit ${editing.name}`;
      $("delete-person").hidden = false;
      renderPhotos();
      $("photo-status").textContent = "Saved. Now add photos so JARVIS can recognize them.";
    } else {
      closeEditor();
    }
  } catch (err) { $("form-error").textContent = err.message; }
});

$("delete-person").addEventListener("click", async () => {
  if (!editing || !confirm(`Delete ${editing.name}? JARVIS will stop recognizing them.`)) return;
  try { await api(`/api/people/${editing.id}`, { method: "DELETE" }); closeEditor(); }
  catch (err) { $("form-error").textContent = err.message; }
});
$("new-person").addEventListener("click", () => openEditor(null));
$("modal-close").addEventListener("click", closeEditor);
$("modal-cancel").addEventListener("click", closeEditor);
$("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeEditor(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("modal").hidden) closeEditor(); });

const dropzone = $("dropzone");
$("photo-input").addEventListener("change", (e) => { uploadPhotos(e.target.files); e.target.value = ""; });
["dragenter", "dragover"].forEach((t) => dropzone.addEventListener(t, (e) => { e.preventDefault(); dropzone.classList.add("over"); }));
["dragleave", "drop"].forEach((t) => dropzone.addEventListener(t, (e) => { e.preventDefault(); dropzone.classList.remove("over"); }));
dropzone.addEventListener("drop", (e) => uploadPhotos(e.dataTransfer.files));
dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("photo-input").click(); } });

$("recognize-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const out = $("recognize-result");
  out.textContent = "Looking…";
  const fd = new FormData(); fd.append("file", file, file.name);
  try { out.textContent = (await api("/api/people/recognize", { method: "POST", form: fd })).summary; }
  catch (err) { out.textContent = err.message; }
});
$("people-search").addEventListener("input", () => { clearTimeout(peopleTimer); peopleTimer = setTimeout(loadPeople, 250); });

function tick() { $("clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
setInterval(tick, 1000); tick();
showTab(location.hash === "#people" ? "people" : "facts");
loadFacts();
loadPeople();
