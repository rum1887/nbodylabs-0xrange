/* NBody Agent — dashboard front-end */
"use strict";

const $ = (id) => document.getElementById(id);
const ACCOUNT_NAME = "NBody Labs";
const chat = $("chat");
const state = { conversationId: null, modelReady: false, sending: false };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function bubble(role, html) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.innerHTML = `<div class="bubble">${html}</div>`;
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return wrap;
}

function thinking(on) {
  let el = $("thinking");
  if (on && !el) {
    el = document.createElement("div");
    el.id = "thinking";
    el.className = "msg assistant";
    el.innerHTML = '<div class="bubble muted">Working…</div>';
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
  } else if (!on && el) {
    el.remove();
  }
}

/* The send lock is cleared by the stream's "end"/"error" events. If the
   connection drops or a handler throws before those arrive, the flag would
   stay true and silently swallow every later message — so back it with a
   watchdog and a reset helper. */
const SEND_TIMEOUT_MS = 180000;
let sendWatchdog = null;

function releaseSendLock(note) {
  clearTimeout(sendWatchdog);
  sendWatchdog = null;
  if (!state.sending) return;
  state.sending = false;
  $("send").disabled = !state.modelReady;
  if (note) bubble("system", `<span class="err">${esc(note)}</span>`);
}

async function send(text) {
  if (state.sending) return;
  const message = (text ?? $("input").value).trim();
  if (!message) return;
  const empty = $("chat-empty");
  if (empty) empty.remove();
  openDrawer();
  bubble("user", esc(message));
  $("input").value = "";
  state.sending = true;
  $("send").disabled = true;
  clearTimeout(sendWatchdog);
  sendWatchdog = setTimeout(() => releaseSendLock(
    "The assistant stopped responding. The send lock was released — try again."),
    SEND_TIMEOUT_MS);

  let res;
  try {
    res = await (await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_id: state.conversationId,
        instruction_hierarchy: $("hierarchy").checked,
      }),
    })).json();
  } catch (e) {
    bubble("assistant", `<span class="err">network error: ${esc(e)}</span>`);
    releaseSendLock();
    return;
  }
  if (res.error) {
    bubble("assistant", `<span class="err">${esc(res.error)}</span>`);
    releaseSendLock();
    return;
  }
  state.conversationId = res.conversation_id;
  thinking(true);

  const es = new EventSource("/api/stream?session=" + encodeURIComponent(res.session));
  es.onmessage = (ev) => {
    let e;
    try { e = JSON.parse(ev.data); } catch { return; }
    const d = e.data || {};
    switch (e.type) {
      case "proposal":
        thinking(false); renderProposal(d); refreshProposals(); break;
      case "ui":
        thinking(false); renderCard(d); break;
      case "injection":
        thinking(false);
        bubble("system", `<b>⚠ Untrusted content detected</b> in the output of
          <code>${esc(d.tool)}</code>.<br><span class="mono small">markers:
          ${esc((d.markers || []).join(", "))}</span>`);
        break;
      case "denied":
        bubble("system", `<b>🔒 Permission denied</b> — ${esc(d.permission)}`);
        break;
      case "tool_error":
        bubble("system", `<span class="err">${esc(d.tool)}: ${esc(d.error)}</span>`);
        break;
      case "final":
        thinking(false);
        const el = bubble("assistant", `<pre class="plain">${esc(d.text)}</pre>`);
        const fb = document.createElement("div");
        fb.className = "feedback";
        fb.innerHTML = `<button data-v="up">👍</button><button data-v="down">👎</button>`;
        fb.querySelectorAll("button").forEach(b => b.onclick = async () => {
          await fetch("/api/feedback", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message_id: d.message_id,
                                   conversation_id: state.conversationId, value: b.dataset.v }),
          });
          fb.innerHTML = "<span class='muted small'>thanks</span>";
        });
        el.querySelector(".bubble").appendChild(fb);
        break;
      case "quality":
        bubble("system", `<b>Quality scorer</b>: ${esc((d.flags || []).join("; "))}`);
        break;
      case "error":
        thinking(false);
        bubble("assistant", `<span class="err">${esc(d.message)}</span>`);
        break;
      case "end":
        thinking(false); es.close();
        releaseSendLock();
        refreshProposals(); refreshChanges();
        break;
    }
  };
  es.onerror = () => {
    es.close(); thinking(false);
    releaseSendLock("Connection to the assistant was lost. Try sending again.");
  };
}

/* ── approval cards ────────────────────────────────────────────────── */

function proposalCard(p, interactive = true) {
  const btns = interactive && p.status === "pending"
    ? `<div class="card-actions">
         <button class="btn primary" data-approve="${p.id}">Approve</button>
         <button class="btn" data-reject="${p.id}">Reject</button>
       </div>`
    : `<div class="card-status">${esc(p.status)}</div>`;
  return `<div class="card proposal">
    <div class="card-head">✋ Approval required — nothing has changed yet</div>
    <div class="card-body"><b>${esc(p.summary)}</b></div>
    <details><summary>Tool &amp; arguments</summary>
      <pre class="mono">${esc(p.tool)}(${esc(JSON.stringify(p.args, null, 2))})</pre></details>
    ${btns}</div>`;
}

function renderProposal(p) {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = `<div class="bubble">I've prepared a change. It will not run until you
    approve it:<div class="card-slot">${proposalCard(p)}</div></div>`;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-approve],[data-reject]");
  if (btn) {
    const action = btn.dataset.approve ? "approve" : "reject";
    const id = btn.dataset.approve || btn.dataset.reject;
    const res = await (await fetch(`/api/proposals/${id}/${action}`, { method: "POST" })).json();
    if (res.error) { alert(res.error); return; }
    if (action === "approve") {
      bubble("system", `<div class="bubble ok"><b>Approved and executed.</b> Change recorded;
        you can propose an undo from the sidebar.</div>`);
    }
    refreshProposals(); refreshChanges();
    return;
  }
  const u = ev.target.closest("[data-undo]");
  if (u) {
    const res = await (await fetch(`/api/changes/${u.dataset.undo}/undo`, { method: "POST" })).json();
    if (res.error) { alert(res.error); return; }
    renderProposal(res.proposal);
    refreshProposals();
  }
});

async function refreshProposals() {
  const list = await (await fetch("/api/proposals")).json();
  const pending = list.filter(p => p.status === "pending");
  $("pending").innerHTML = pending.length
    ? pending.map(p => proposalCard(p)).join("")
    : '<p class="muted small">Nothing waiting.</p>';
  const badge = $("nav-approvals");
  if (badge) {
    badge.textContent = pending.length;
    badge.dataset.n = pending.length;
  }
}

async function refreshChanges() {
  const list = await (await fetch("/api/changes")).json();
  $("changes").innerHTML = list.length
    ? list.map(c => `<div class="card small-card">
        <div>${esc(c.summary)}</div>
        <div class="card-status">applied ${esc(c.created)}</div>
        <button class="btn" data-undo="${c.id}">Propose undo</button>
      </div>`).join("")
    : '<p class="muted small">No changes applied yet.</p>';
}

/* ── generative UI cards ───────────────────────────────────────────── */

function renderCard(d) {
  let inner = "";
  if (d.ui_type === "table") {
    const cols = d.columns || [];
    inner = `<table class="tbl"><thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${(d.rows || []).map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  } else if (d.ui_type === "metric") {
    inner = `<div class="metrics">${(d.metrics || []).map(m =>
      `<div class="metric"><div class="mv">${esc(m.value)}</div><div class="ml">${esc(m.label)}</div></div>`).join("")}</div>`;
  } else if (d.ui_type === "chart") {
    const rows = d.rows || [];
    const nums = rows.map(r => parseFloat(String(r[1] ?? 0)) || 0);
    const max = Math.max(1, ...nums);
    inner = `<div class="chart">${rows.map((r, i) =>
      `<div class="bar" title="${esc(r[1])}"><div class="fill" style="height:${(nums[i] / max) * 100}%"></div>
        <span class="bl">${esc(r[0])}</span></div>`).join("")}</div>`;
  }
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = `<div class="card wide">
    <div class="card-head">${esc(d.title)}</div>${inner}
    ${d.note ? `<div class="muted small">${esc(d.note)}</div>` : ""}
    <div class="card-status">Generative UI card · click to open full screen</div></div>`;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

/* ── permissions ───────────────────────────────────────────────────── */

async function renderPermissions() {
  const p = await (await fetch("/api/permissions")).json();
  document.querySelectorAll('input[name="tpl"]').forEach(r =>
    r.checked = (r.value === p.template));
  $("perm-list").innerHTML = `<div class="perm-head">Permissions held by this token</div>` +
    Object.entries(p.catalogue).map(([perm, desc]) => `
      <label class="perm">
        <input type="checkbox" data-perm="${perm}" ${p.scopes.includes(perm) ? "checked" : ""}>
        <span><b>${esc(perm)}</b> <span class="muted small">${esc(desc)}</span></span>
      </label>`).join("");
  $("write-lock").checked = !!p.write_locked;
  $("token-name").textContent = p.token_name || "(none yet)";
  $("pill-write").textContent = p.write_locked ? "writes: OFF (admin)" : "writes: available";
  $("pill-write").className = "pill" + (p.write_locked ? " warn" : " ok");
}

document.addEventListener("change", async (ev) => {
  if (ev.target.name === "tpl") {
    await fetch("/api/permissions/template", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template: ev.target.value }),
    });
    renderPermissions();
  } else if (ev.target.id === "write-lock") {
    await fetch("/api/permissions/write-lock", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: ev.target.checked }),
    });
    renderPermissions();
  } else if (ev.target.dataset.perm) {
    const granted = [...document.querySelectorAll("[data-perm]")]
      .filter(c => c.checked).map(c => c.dataset.perm);
    await fetch("/api/permissions/custom", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ granted }),
    });
    renderPermissions();
  }
});

/* ── evals + history ───────────────────────────────────────────────── */

async function renderEvals() {
  const e = await (await fetch("/api/evals")).json();
  const rate = e.tool_call_success_rate == null ? "—"
    : Math.round(e.tool_call_success_rate * 100) + "%";
  const cells = [
    ["model", e.model],
    ["model requests", e.requests],
    ["failed requests", e.failed_requests],
    ["avg latency", (e.avg_latency_ms ?? "—") + " ms"],
    ["tool-call success", rate],
    ["thumbs up / down", `${(e.feedback.up || 0)} / ${(e.feedback.down || 0)}`],
  ];
  $("statgrid").innerHTML = cells.map(([k, v]) =>
    `<div class="stat"><div class="mv">${esc(v)}</div><div class="ml">${esc(k)}</div></div>`).join("");

  const audit = await (await fetch("/api/audit")).json();
  $("audit").querySelector("tbody").innerHTML = audit.slice(-25).reverse().map(a => {
    const detail = a.record ? JSON.stringify(a.record) : (a.reason || a.target || "");
    return `<tr><td class="mono small">${esc(a.at)}</td><td>${esc(eventLabel(a.event))}</td>
      <td class="mono small">${esc(detail).slice(0, 120)}</td></tr>`;
  }).join("");
}

async function renderHistory() {
  const list = await (await fetch("/api/conversations")).json();
  $("convos").querySelector("tbody").innerHTML = list.map(c => `
    <tr><td>${esc(c.title)}</td><td class="mono small">${esc(c.created)}</td>
    <td class="mono small">${esc(c.updated)}</td>
    <td><button class="btn" data-conv="${c.id}">open</button></td></tr>`).join("");
}

/* Replays a stored conversation into the drawer: every message the model
   produced, plus any approval cards that belong to that conversation. */
async function openConversation(id) {
  state.conversationId = id;
  chat.innerHTML = "";
  openDrawer();
  bubble("system", "Loading conversation…");

  let data;
  try {
    data = await (await fetch("/api/conversations/" + encodeURIComponent(id))).json();
  } catch (e) {
    chat.innerHTML = "";
    bubble("assistant", `<span class="err">could not load conversation: ${esc(e)}</span>`);
    return;
  }
  if (data.error) {
    chat.innerHTML = "";
    bubble("assistant", `<span class="err">${esc(data.error)}</span>`);
    return;
  }

  chat.innerHTML = "";
  const msgs = data.messages || [];
  if (!msgs.length) {
    bubble("system", `This conversation <span class="mono">${esc(id)}</span> has no messages yet.`);
    return;
  }

  // Proposals are linked to a conversation, not to a specific message id, so
  // attach each card to the assistant turn that was current when it was created.
  const proposals = (data.proposals || []).slice()
    .sort((a, b) => String(a.created).localeCompare(String(b.created)));
  let pi = 0;

  msgs.forEach(m => {
    if (m.role === "user") {
      bubble("user", esc(m.content));
      return;
    }
    if (m.role === "assistant") {
      const el = bubble("assistant", `<pre class="plain">${esc(m.content)}</pre>`);
      while (pi < proposals.length &&
             String(proposals[pi].created) <= String(m.created)) {
        const p = proposals[pi++];
        const slot = document.createElement("div");
        slot.className = "card-slot";
        slot.innerHTML = proposalCard(p, p.status === "pending");
        el.querySelector(".bubble").appendChild(slot);
      }
      return;
    }
    if (m.role === "system") bubble("system", esc(m.content));
  });

  // anything created after the last message still belongs to this conversation
  while (pi < proposals.length) {
    const p = proposals[pi++];
    const slot = document.createElement("div");
    slot.className = "card-slot";
    slot.innerHTML = proposalCard(p, p.status === "pending");
    chat.appendChild(slot);
  }

  bubble("system", `Replayed <b>${msgs.length}</b> message${msgs.length === 1 ? "" : "s"} from
    <span class="mono">${esc(id)}</span>.`);
}

document.addEventListener("click", (ev) => {
  const c = ev.target.closest("[data-conv]");
  if (!c) return;
  openConversation(c.dataset.conv);
  $("input").focus();
});

/* ── account home ───────────────────────────────────────────────────── */

const EVENT_LABELS = {
  token_created: "Access token created",
  token_deleted: "Access token revoked",
  dns_create: "DNS record created",
  dns_update: "DNS record updated",
  dns_delete: "DNS record deleted",
  settings_update: "Zone settings updated",
  security_rule_update: "Security rule updated",
  cache_rule_update: "Cache rule updated",
  support_case: "Support case submitted",
  write_lock: "Write access toggled",
  denied: "Request denied by permissions",
};

function eventLabel(e) {
  return EVENT_LABELS[e] || e.replace(/_/g, " ");
}

async function renderHome() {
  const s = await (await fetch("/api/status")).json();
  const proposals = await (await fetch("/api/proposals")).json();
  const changes = await (await fetch("/api/changes")).json();
  const audit = await (await fetch("/api/audit")).json();
  const pending = proposals.filter(p => p.status === "pending").length;

  $("home-stats").innerHTML = [
    ["Account", s.cf_api ? "Connected" : "Offline"],
    ["Pending approvals", pending],
    ["Applied changes", changes.length],
    ["Assistant", s.model_ready ? "Ready" : "Loading"],
  ].map(([k, v]) => `<div class="stat"><div class="mv">${esc(v)}</div>
      <div class="ml">${esc(k)}</div></div>`).join("");

  const recent = audit.slice(-10).reverse();
  $("home-activity").innerHTML = recent.length
    ? recent.map(a => `<li><span class="when">${esc(String(a.at).slice(5, 16))}</span>
        <span class="what">${esc(eventLabel(a.event))}</span></li>`).join("")
    : '<li class="muted small">No activity yet.</li>';
}

/* ── tabs + boot ───────────────────────────────────────────────────── */

const TAB_LABELS = {
  home: "Account home", approvals: "Approval centre",
  access: "Access & permissions", evals: "Quality & evals", history: "Conversations",
};

function openDrawer() {
  appEl.classList.remove("drawer-hidden");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".pane").forEach(p =>
    p.classList.toggle("active", p.id === "tab-" + name));
  if (TAB_LABELS[name]) $("crumb").textContent = TAB_LABELS[name];
  if (location.hash.slice(1) !== name) history.replaceState(null, "", "#" + name);
  if (name === "home") renderHome();
  if (name === "approvals") { refreshProposals(); refreshChanges(); }
  if (name === "access") renderPermissions();
  if (name === "evals") renderEvals();
  if (name === "history") renderHistory();
}

async function refreshStatus() {
  let s;
  try {
    s = await (await fetch("/api/status", { cache: "no-store" })).json();
  } catch {
    return; // transient network blip; keep the current button state
  }
  state.modelReady = !!s.model_ready;
  $("pill-model").textContent = "model: " + s.model + (s.model_ready ? " ✓" : " …");
  $("pill-model").className = "pill" + (s.model_ready ? " ok" : "");
  $("model-warning").hidden = !!s.model_ready;
  $("send").disabled = !s.model_ready || state.sending;
  $("pill-account").textContent = ACCOUNT_NAME + " · Pro";
  $("pill-account").className = "pill" + (s.cf_api ? " ok" : " warn");
}

document.querySelectorAll(".tab").forEach(t => t.onclick = () => switchTab(t.dataset.tab));
document.querySelectorAll(".chip").forEach(c => c.onclick = () => send(c.dataset.q));
document.querySelectorAll(".tile[data-q]").forEach(t => t.onclick = () => send(t.dataset.q));
$("send").onclick = () => send();
$("input").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
// assistant drawer controls
const appEl = document.querySelector(".app");
$("ask-btn").onclick = () => { openDrawer(); $("input").focus(); };
$("drawer-close").onclick = () => appEl.classList.add("drawer-hidden");

/* Drawer sizing. Three inputs share one --drawer-w column:
   1. the CSS default (400px), 2. the expand preset (.drawer-wide),
   3. an inline pixel value set by dragging the left edge.
   A manual drag wins, so it clears the preset class. */
const expandBtn = $("drawer-expand");
const resizer = $("drawer-resize");
const DRAWER_MIN = 340;
const DRAWER_MAX = 1400;

function clampDrawer(px) {
  // leave the nav rail and a usable sliver of content on screen
  const room = Math.max(DRAWER_MIN, window.innerWidth - 300);
  return Math.round(Math.max(DRAWER_MIN, Math.min(DRAWER_MAX, room, px)));
}
function saveDrawerPref(pref) {
  try { localStorage.setItem("nbody.drawer", JSON.stringify(pref)); } catch {}
}
function setExpandIcon(on) {
  expandBtn.querySelector("use").setAttribute("href", on ? "#i-col" : "#i-exp");
  expandBtn.title = on ? "Collapse assistant" : "Expand assistant";
}
function setDrawerWide(on) {
  appEl.style.removeProperty("--drawer-w");
  appEl.classList.remove("drawer-takeover");
  appEl.classList.toggle("drawer-wide", on);
  setExpandIcon(on);
  saveDrawerPref({ wide: on });
}
function setDrawerWidth(px) {
  const w = clampDrawer(px);
  appEl.classList.remove("drawer-wide"); // manual sizing overrides the preset
  appEl.style.setProperty("--drawer-w", w + "px");
  // once the content pane would be squeezed to a sliver, let the assistant
  // take the whole column instead of shrinking into an unusable strip
  appEl.classList.toggle("drawer-takeover", !isPhone() && w >= window.innerWidth - 560);
  setExpandIcon(false);
  saveDrawerPref({ px: w });
}
expandBtn.onclick = () => {
  const wide = appEl.classList.contains("drawer-wide");
  if (wide) appEl.style.removeProperty("--drawer-w");
  setDrawerWide(!wide);
};

/* Drag the left edge. Pointer events cover mouse, touch and pen; the column
   transition is switched off while dragging so it tracks the cursor. */
resizer.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  e.preventDefault();
  try { resizer.setPointerCapture(e.pointerId); } catch {}
  const startX = e.clientX;
  const startW = $("drawer").getBoundingClientRect().width;
  appEl.classList.add("is-resizing");
  const body = document.body;
  const prevCursor = body.style.cursor, prevSelect = body.style.userSelect;
  body.style.cursor = "col-resize";
  body.style.userSelect = "none";

  const move = (ev) => setDrawerWidth(startW + (startX - ev.clientX));
  const up = () => {
    resizer.removeEventListener("pointermove", move);
    resizer.removeEventListener("pointerup", up);
    resizer.removeEventListener("pointercancel", up);
    appEl.classList.remove("is-resizing");
    body.style.cursor = prevCursor;
    body.style.userSelect = prevSelect;
    // each move already persists the width; re-reading the rendered box here
    // can capture a stale value, so do not re-measure
  };
  resizer.addEventListener("pointermove", move);
  resizer.addEventListener("pointerup", up);
  resizer.addEventListener("pointercancel", up);
});

// double-click the handle returns to the default width
resizer.addEventListener("dblclick", () => {
  appEl.style.removeProperty("--drawer-w");
  setDrawerWide(false);
});

// keyboard resize for accessibility
resizer.addEventListener("keydown", (e) => {
  const step = e.shiftKey ? 64 : 24;
  const w = $("drawer").getBoundingClientRect().width;
  if (e.key === "ArrowLeft") { e.preventDefault(); setDrawerWidth(w + step); }
  else if (e.key === "ArrowRight") { e.preventDefault(); setDrawerWidth(w - step); }
});

// keep a manual width inside the viewport when the window changes
window.addEventListener("resize", () => {
  const inline = appEl.style.getPropertyValue("--drawer-w");
  if (inline) setDrawerWidth(parseFloat(inline));
});

$("drawer-refresh").onclick = () => {
  state.conversationId = null;
  chat.innerHTML = "";
  bubble("assistant", "New conversation. What would you like to look at?");
  $("input").focus();
};
$("drawer-title").onclick = () => $("drawer-refresh").click();

// hero + quick search both route into the assistant
[$("hero-input"), $("quick-search")].forEach(el => {
  el.addEventListener("keydown", e => {
    if (e.key !== "Enter") return;
    const q = el.value.trim();
    if (!q) return;
    el.value = "";
    send(q);
  });
});

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    ($("quick-search").value ? $("quick-search") : $("hero-input")).focus();
  }
  // on phones the drawer covers the page, so Escape must close it
  if (e.key === "Escape" && isPhone()) {
    appEl.classList.add("drawer-hidden");
  }
});

const isPhone = () =>
  typeof window.matchMedia === "function"
    ? window.matchMedia("(max-width: 760px)").matches
    : window.innerWidth <= 760;

(async function init() {
  // on phones the drawer is a full-screen overlay, so start with it closed
  if (isPhone()) appEl.classList.add("drawer-hidden");
  // restore the saved drawer size
  try {
    const pref = JSON.parse(localStorage.getItem("nbody.drawer") || "{}");
    if (typeof pref.px === "number") setDrawerWidth(pref.px);
    else if (pref.wide) setDrawerWide(true);
  } catch {}
  const h = new Date().getHours();
  $("greeting").textContent =
    h < 5 ? "Working late?" : h < 12 ? "Good morning." : h < 18 ? "Good afternoon." : "Good evening.";
  const start = location.hash.slice(1);
  refreshStatus();
  setInterval(refreshStatus, 5000);
  refreshProposals();
  refreshChanges();
  renderHome();
  renderPermissions();
  if (TAB_LABELS[start]) switchTab(start);
})();