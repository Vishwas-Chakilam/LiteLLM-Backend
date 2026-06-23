const API = {
  token: () => localStorage.getItem("admin_token"),

  async request(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...options.headers };
    const token = this.token();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(path, { ...options, headers });
    if (res.status === 401) {
      logout();
      throw new Error("Session expired. Please log in again.");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    return res.json();
  },

  get: (path) => API.request(path),
  patch: (path, body) => API.request(path, { method: "PATCH", body: JSON.stringify(body) }),
  post: (path, body) => API.request(path, { method: "POST", body: JSON.stringify(body) }),
};

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function showLogin() {
  $("#login-screen").style.display = "flex";
  $("#app").classList.remove("active");
}

function showApp(user) {
  $("#login-screen").style.display = "none";
  $("#app").classList.add("active");
  $("#user-email").textContent = user?.email || "Dev Admin";
  $("#user-role").textContent = user?.role || "admin";
}

function logout() {
  localStorage.removeItem("admin_token");
  localStorage.removeItem("admin_user");
  showLogin();
}

async function tryAutoLogin() {
  const token = API.token();
  if (!token) return showLogin();
  try {
    const user = await API.get("/auth/me");
    if (user.role !== "admin") {
      alert("Admin access required.");
      return logout();
    }
    localStorage.setItem("admin_user", JSON.stringify(user));
    showApp(user);
    loadSection("dashboard");
  } catch {
    showLogin();
  }
}

$("#login-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("#login-email").value;
  const password = $("#login-password").value;
  const errEl = $("#login-error");
  errEl.textContent = "";
  try {
    const data = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then((r) => r.json());
    if (data.detail) throw new Error(data.detail);
    if (data.user?.role !== "admin") throw new Error("This account is not an admin.");
    localStorage.setItem("admin_token", data.access_token);
    localStorage.setItem("admin_user", JSON.stringify(data.user));
    showApp(data.user);
    loadSection("dashboard");
  } catch (err) {
    errEl.textContent = err.message;
    errEl.style.display = "block";
  }
});

$("#logout-btn")?.addEventListener("click", logout);

$$(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => loadSection(btn.dataset.section));
});

const titles = {
  dashboard: "Dashboard",
  playground: "Agent Playground",
  users: "Users",
  patients: "Patient Profiles",
  conversations: "Conversations",
  agents: "Agent Registry",
  prior_auth: "Prior Authorizations",
  workflows: "Workflow Runs",
  audit: "Audit Logs",
  agent_logs: "Agent Execution Logs",
  tool_logs: "Tool Logs",
  assignments: "Doctor Assignments",
  cost: "LLM Costs",
};

function loadSection(name) {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.section === name));
  $$(".section").forEach((s) => s.classList.toggle("active", s.id === `section-${name}`));
  $("#page-title").textContent = titles[name] || name;
  const loaders = {
    dashboard: loadDashboard,
    playground: initPlayground,
    users: loadUsers,
    patients: loadPatients,
    conversations: loadConversations,
    agents: loadAgents,
    prior_auth: loadPriorAuth,
    workflows: loadWorkflows,
    audit: () => loadTable("audit", "/admin/api/audit-logs", auditCols),
    agent_logs: () => loadTable("agent_logs", "/admin/api/agent-logs", agentLogCols),
    tool_logs: () => loadTable("tool_logs", "/admin/api/tool-logs", toolLogCols),
    assignments: loadAssignments,
    cost: loadCost,
  };
  loaders[name]?.();
}

function badge(val, prefix = "") {
  const cls = `${prefix}${(val || "unknown").toLowerCase().replace(/\s/g, "_")}`;
  return `<span class="badge badge-${cls}">${val || "—"}</span>`;
}

function fmtDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleString();
}

function trunc(s, n = 60) {
  if (!s) return "—";
  const t = typeof s === "object" ? JSON.stringify(s) : String(s);
  return t.length > n ? t.slice(0, n) + "…" : t;
}

function renderTable(containerId, rows, cols) {
  const el = $(`#${containerId}-table`);
  if (!rows?.length) {
    el.innerHTML = '<div class="empty">No records found.</div>';
    return;
  }
  const head = cols.map((c) => `<th>${c.label}</th>`).join("");
  const body = rows.map((row) => {
    const cells = cols.map((c) => `<td>${c.render(row)}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");
  el.innerHTML = `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

async function loadTable(id, url, cols) {
  const el = $(`#${id}-table`);
  el.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const rows = await API.get(url);
    renderTable(id, rows, cols);
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

async function loadDashboard() {
  try {
    const s = await API.get("/admin/api/stats");
    $("#stats-grid").innerHTML = `
      <div class="stat-card"><div class="label">Users</div><div class="value">${s.users}</div></div>
      <div class="stat-card"><div class="label">Conversations</div><div class="value">${s.conversations}</div><div class="sub">${s.file_conversations} file-based (legacy)</div></div>
      <div class="stat-card"><div class="label">Messages</div><div class="value">${s.messages}</div></div>
      <div class="stat-card"><div class="label">Prior Auth</div><div class="value">${s.prior_authorizations}</div></div>
      <div class="stat-card"><div class="label">Workflows</div><div class="value">${s.workflow_runs}</div></div>
      <div class="stat-card"><div class="label">Active Agents</div><div class="value">${s.active_agents}</div></div>
      <div class="stat-card"><div class="label">Daily Spend</div><div class="value">$${s.daily_spend_usd}</div><div class="sub">Budget: $${s.daily_budget_usd}</div></div>
      <div class="stat-card"><div class="label">Audit Events</div><div class="value">${s.audit_logs}</div></div>
    `;
    const warn = $("#supabase-warn");
    if (!s.supabase_configured) {
      warn.style.display = "block";
      warn.textContent = "Supabase is not configured — database stats show 0. File-based conversations and in-memory agents still work.";
    } else {
      warn.style.display = "none";
    }
  } catch (err) {
    $("#stats-grid").innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

const userCols = [
  { label: "Email", render: (r) => r.email },
  { label: "Name", render: (r) => r.full_name || "—" },
  { label: "Role", render: (r) => badge(r.role) },
  { label: "Organization", render: (r) => r.organization || "—" },
  { label: "Created", render: (r) => fmtDate(r.created_at) },
  {
    label: "Actions",
    render: (r) => `<select onchange="updateRole('${r.id}', this.value)" style="width:auto">
      ${["patient","doctor","admin","insurance_agent","support"].map((ro) =>
        `<option value="${ro}" ${r.role === ro ? "selected" : ""}>${ro}</option>`).join("")}
    </select>`,
  },
];

async function loadUsers() { await loadTable("users", "/admin/api/users", userCols); }

window.updateRole = async (id, role) => {
  try {
    await API.patch(`/admin/api/users/${id}`, { role });
  } catch (err) {
    alert(err.message);
    loadUsers();
  }
};

const patientCols = [
  { label: "ID", render: (r) => trunc(r.id, 12) },
  { label: "User ID", render: (r) => trunc(r.user_id, 12) },
  { label: "Age", render: (r) => r.age ?? "—" },
  { label: "Gender", render: (r) => r.gender || "—" },
  { label: "Insurer", render: (r) => r.insurance_provider || "—" },
  { label: "Allergies", render: (r) => trunc(r.allergies) },
  { label: "Updated", render: (r) => fmtDate(r.updated_at) },
];

async function loadPatients() { await loadTable("patients", "/admin/api/patients", patientCols); }

const convCols = [
  { label: "Title", render: (r) => r.title || "—" },
  { label: "Status", render: (r) => badge(r.status) },
  { label: "Session", render: (r) => trunc(r.session_id, 16) },
  { label: "User", render: (r) => trunc(r.user_id, 12) },
  { label: "Updated", render: (r) => fmtDate(r.updated_at) },
  {
    label: "",
    render: (r) => `<button class="btn btn-ghost btn-sm" onclick="viewMessages('${r.id}')">Messages</button>`,
  },
];

async function loadConversations() { await loadTable("conversations", "/admin/api/conversations", convCols); }

window.viewMessages = async (id) => {
  try {
    const msgs = await API.get(`/admin/api/conversations/${id}/messages`);
    const text = msgs.map((m) => `[${m.sender_type}] ${m.message}`).join("\n\n") || "No messages.";
    alert(text.slice(0, 2000));
  } catch (err) {
    alert(err.message);
  }
};

const agentCols = [
  { label: "Agent ID", render: (r) => r.agent_id || "—" },
  { label: "Name", render: (r) => r.name },
  { label: "Domain", render: (r) => r.domain },
  { label: "Model", render: (r) => r.preferred_model || "—" },
  { label: "Priority", render: (r) => r.priority ?? 0 },
  { label: "Safety", render: (r) => r.safety_level || "—" },
  { label: "Active", render: (r) => badge(r.is_active !== false ? "active" : "failed") },
  {
    label: "",
    render: (r) => `<button class="btn btn-ghost btn-sm" onclick="testAgent('${r.agent_id}')">Test</button>`,
  },
];

async function loadAgents() { await loadTable("agents", "/admin/api/agents", agentCols); }

window.testAgent = (agentId) => {
  loadSection("playground");
  setPlaygroundMode("agent");
  $("#playground-agent").value = agentId;
  $("#playground-query").focus();
};

/* ── Agent Playground ── */

let playgroundMode = "workflow";
let playgroundSamples = [];

function setPlaygroundMode(mode) {
  playgroundMode = mode;
  $$(".mode-tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === mode));
  $("#agent-select-group").style.display = mode === "agent" ? "block" : "none";
  const queryGroup = $("#playground-query")?.closest(".form-group");
  const sampleGroup = $("#sample-prompts")?.closest(".form-group");
  if (queryGroup) queryGroup.style.display = mode === "health" ? "none" : "block";
  if (sampleGroup) sampleGroup.style.display = mode === "health" ? "none" : "block";
}

async function initPlayground() {
  if (!playgroundSamples.length) {
    try {
      playgroundSamples = await API.get("/admin/api/playground/samples");
    } catch { playgroundSamples = []; }
  }
  renderSampleChips();
  await populateAgentSelect();
  await populateDemoPatients();
  setPlaygroundMode(playgroundMode);
}

async function populateAgentSelect() {
  const sel = $("#playground-agent");
  if (!sel) return;
  try {
    const agents = await API.get("/admin/api/agents");
    sel.innerHTML = agents.map((a) =>
      `<option value="${a.agent_id}">${a.name || a.agent_id} (${a.domain})</option>`
    ).join("");
  } catch {
    sel.innerHTML = "<option value=''>Failed to load agents</option>";
  }
}

async function populateDemoPatients() {
  const sel = $("#playground-demo-patient");
  if (!sel) return;
  try {
    const demos = await API.get("/admin/api/hospital/demo-patients");
    sel.innerHTML = demos.map((d, i) =>
      `<option value="${i}">${d.name} — ${d.insurance_provider || "no insurer"}</option>`
    ).join("");
  } catch {
    sel.innerHTML = '<option value="0">Jane Demo — aetna</option><option value="1">John Demo — united</option>';
  }
}

function renderSampleChips() {
  const el = $("#sample-prompts");
  if (!el) return;
  el.innerHTML = playgroundSamples.map((s) =>
    `<button type="button" class="chip" data-id="${s.id}">${s.label}</button>`
  ).join("");
  el.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const sample = playgroundSamples.find((s) => s.id === chip.dataset.id);
      if (!sample) return;
      $("#playground-query").value = sample.query;
      if (sample.suggested_mode) setPlaygroundMode(sample.suggested_mode);
      if (sample.suggested_agent) $("#playground-agent").value = sample.suggested_agent;
    });
  });
}

$$(".mode-tab").forEach((tab) => {
  tab.addEventListener("click", () => setPlaygroundMode(tab.dataset.mode));
});

function setPlaygroundStatus(status, ok) {
  const el = $("#playground-status");
  el.textContent = status;
  el.className = "badge " + (ok === true ? "badge-active" : ok === false ? "badge-failed" : "badge-pending");
}

function renderPlaygroundResult(data) {
  const el = $("#playground-result");

  if (data.mode === "health" || (data.agents && !data.agent_results)) {
    const health = data.agents ? data : data;
    setPlaygroundStatus(health.healthy ? "all ready" : "issues found", health.healthy);
    el.innerHTML = `
      <div class="result-meta">
        <div class="meta-item"><strong>Ready</strong>${health.ready_count} / ${health.agent_count}</div>
      </div>
      <div class="health-grid">
        ${health.agents.map((a) => `
          <div class="health-row">
            <span>${a.name || a.agent_id} <span style="color:var(--muted)">(${a.domain})</span></span>
            ${badge(a.status)}
          </div>
        `).join("")}
      </div>`;
    return;
  }

  setPlaygroundStatus(
    data.out_of_scope ? "out of scope" : (data.success ? "success" : "failed"),
    data.out_of_scope ? null : data.success
  );

  let html = `<div class="result-meta">
    <div class="meta-item"><strong>Duration</strong>${data.duration_ms} ms</div>
    <div class="meta-item"><strong>Mode</strong>${data.mode}</div>`;
  if (data.intent) html += `<div class="meta-item"><strong>Intent</strong>${data.intent}</div>`;
  if (data.urgency && data.urgency !== "n/a") html += `<div class="meta-item"><strong>Urgency</strong>${badge(data.urgency)}</div>`;
  if (data.emergency) html += `<div class="meta-item"><strong>Escalated</strong>${badge("failed")} emergency</div>`;
  if (data.workflow_id) html += `<div class="meta-item"><strong>Workflow ID</strong>${trunc(data.workflow_id, 20)}</div>`;
  html += `</div>`;

  if (data.out_of_scope) {
    html += `<div class="alert alert-warn">Out of scope — healthcare queries only. No agents were run.</div>`;
  } else if (data.selected_agents?.length) {
    html += `<p style="font-size:0.8125rem;color:var(--muted);margin-bottom:0.75rem">
      <strong>Selected:</strong> ${data.selected_agents.join(" → ")}
    </p>`;
  }

  if (data.final_output) {
    html += `<div class="result-final"><strong>Final response</strong><br><br>${escapeHtml(data.final_output)}</div>`;
  }

  if (data.errors?.length) {
    html += `<div class="alert alert-error">${data.errors.map(escapeHtml).join("<br>")}</div>`;
  }

  if (data.agent_results?.length) {
    html += `<h4 style="font-size:0.875rem;margin-bottom:0.5rem">Agent outputs</h4>`;
    data.agent_results.forEach((ar, i) => {
      const out = JSON.stringify(ar.output || {}, null, 2);
      html += `
        <div class="agent-result-card ${i === 0 ? "open" : ""}" onclick="this.classList.toggle('open')">
          <div class="agent-result-header">
            <span>${ar.agent_id || ar.name || "agent"}</span>
            <span>${badge(ar.status)} ${ar.duration_ms ? ar.duration_ms + "ms" : ""}</span>
          </div>
          <div class="agent-result-body">${escapeHtml(ar.error || out)}</div>
        </div>`;
    });
  }

  el.innerHTML = html;
}

function escapeHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

async function runPlayground(mode) {
  const resultEl = $("#playground-result");
  resultEl.innerHTML = '<div class="empty">Running… this may take 15–30s while agents call the LLM.</div>';
  setPlaygroundStatus("running", null);

  const body = { mode: mode || playgroundMode };
  const demoIdx = $("#playground-demo-patient")?.value;
  if (demoIdx !== undefined && demoIdx !== "") {
    body.demo_patient_index = parseInt(demoIdx, 10);
  }
  if (body.mode !== "health") {
    body.query = $("#playground-query").value.trim();
    if (!body.query) {
      resultEl.innerHTML = '<div class="alert alert-error">Enter a query first.</div>';
      setPlaygroundStatus("idle", null);
      return;
    }
  }
  if (body.mode === "agent") {
    body.agent_id = $("#playground-agent").value;
    if (!body.agent_id) {
      resultEl.innerHTML = '<div class="alert alert-error">Select an agent.</div>';
      setPlaygroundStatus("idle", null);
      return;
    }
  }

  $("#playground-run").disabled = true;
  try {
    const data = await API.post("/admin/api/playground/run", body);
    renderPlaygroundResult(data);
  } catch (err) {
    resultEl.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
    setPlaygroundStatus("failed", false);
  } finally {
    $("#playground-run").disabled = false;
  }
}

$("#playground-run")?.addEventListener("click", () => runPlayground());
$("#playground-health")?.addEventListener("click", () => runPlayground("health"));

const paCols = [
  { label: "Insurer", render: (r) => r.insurer },
  { label: "Status", render: (r) => badge(r.status) },
  { label: "Approval %", render: (r) => r.approval_probability != null ? `${(r.approval_probability * 100).toFixed(0)}%` : "—" },
  { label: "Denial Risk", render: (r) => r.denial_risk || "—" },
  { label: "ICD", render: (r) => trunc(r.diagnosis_codes) },
  { label: "CPT", render: (r) => trunc(r.procedure_codes) },
  { label: "Updated", render: (r) => fmtDate(r.updated_at) },
];

async function loadPriorAuth() { await loadTable("prior_auth", "/admin/api/prior-auth", paCols); }

const wfCols = [
  { label: "Workflow", render: (r) => r.workflow_name },
  { label: "Status", render: (r) => badge(r.status) },
  { label: "Conversation", render: (r) => trunc(r.conversation_id, 12) },
  { label: "Started", render: (r) => fmtDate(r.started_at) },
  { label: "Completed", render: (r) => fmtDate(r.completed_at) },
  { label: "State", render: (r) => `<div class="json-cell">${trunc(r.state, 80)}</div>` },
];

async function loadWorkflows() { await loadTable("workflows", "/admin/api/workflows", wfCols); }

const auditCols = [
  { label: "Action", render: (r) => r.action },
  { label: "Resource", render: (r) => `${r.resource_type || ""} ${trunc(r.resource_id, 12)}` },
  { label: "User", render: (r) => trunc(r.user_id, 12) },
  { label: "Time", render: (r) => fmtDate(r.created_at) },
  { label: "Meta", render: (r) => `<div class="json-cell">${trunc(r.metadata, 60)}</div>` },
];

const agentLogCols = [
  { label: "Agent", render: (r) => r.agent_id },
  { label: "Status", render: (r) => badge(r.status) },
  { label: "Time (ms)", render: (r) => r.execution_time_ms ?? "—" },
  { label: "Input", render: (r) => `<div class="json-cell">${trunc(r.input, 50)}</div>` },
  { label: "Output", render: (r) => `<div class="json-cell">${trunc(r.output, 50)}</div>` },
  { label: "At", render: (r) => fmtDate(r.created_at) },
];

const toolLogCols = [
  { label: "Tool", render: (r) => r.tool_name },
  { label: "Agent", render: (r) => r.agent_id || "—" },
  { label: "Status", render: (r) => badge(r.status) },
  { label: "Request", render: (r) => `<div class="json-cell">${trunc(r.request, 50)}</div>` },
  { label: "At", render: (r) => fmtDate(r.created_at) },
];

async function loadAssignments() {
  await loadTable("assignments", "/admin/api/assignments", [
    { label: "Doctor", render: (r) => trunc(r.doctor_id, 16) },
    { label: "Patient", render: (r) => trunc(r.patient_id, 16) },
    { label: "Assigned", render: (r) => fmtDate(r.assigned_at) },
  ]);
}

$("#assignment-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await API.post("/admin/api/assignments", {
      doctor_id: $("#assign-doctor").value,
      patient_id: $("#assign-patient").value,
    });
    $("#assign-doctor").value = "";
    $("#assign-patient").value = "";
    loadAssignments();
  } catch (err) {
    alert(err.message);
  }
});

async function loadCost() {
  const el = $("#cost-table");
  el.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const data = await API.get("/admin/api/cost");
  $("#cost-summary").innerHTML = `
      <div class="stat-card"><div class="label">Daily Spend</div><div class="value">$${data.daily_spend_usd.toFixed(4)}</div></div>
      <div class="stat-card"><div class="label">Budget</div><div class="value">$${data.daily_budget_usd}</div></div>
      <div class="stat-card"><div class="label">File Conversations</div><div class="value">${data.conversation_count}</div></div>
    `;
    renderTable("cost", data.conversations, [
      { label: "Conversation", render: (r) => trunc(r.conversation_id, 16) },
      { label: "Turns", render: (r) => r.turn_count },
      { label: "Cost USD", render: (r) => `$${(r.total_cost_usd || 0).toFixed(6)}` },
      { label: "Updated", render: (r) => r.updated_at || "—" },
    ]);
  } catch (err) {
    el.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

// Dev mode: skip login if no token and auth not required
(async () => {
  const token = API.token();
  if (token) {
    await tryAutoLogin();
  } else {
    try {
      const stats = await fetch("/admin/api/stats").then((r) => {
        if (r.ok) return r.json();
        throw new Error("auth required");
      });
      showApp({ email: "dev@localhost", role: "admin" });
      loadSection("dashboard");
    } catch {
      showLogin();
    }
  }
})();
