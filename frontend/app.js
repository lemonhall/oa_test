const $ = (sel) => document.querySelector(sel);

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data?.error || "request_failed");
    err.code = data?.error || "request_failed";
    throw err;
  }
  return data;
}

function fmtTime(ts) {
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

function setError(el, msg) {
  el.textContent = msg || "";
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onerror = () => reject(r.error || new Error("read_failed"));
    r.onload = () => {
      const s = String(r.result || "");
      const i = s.indexOf(",");
      resolve(i >= 0 ? s.slice(i + 1) : s);
    };
    r.readAsDataURL(file);
  });
}

function badgeClass(status) {
  return status === "approved" ? "approved" : status === "rejected" ? "rejected" : "pending";
}

function statusText(status) {
  return status === "approved" ? "已通过" : status === "rejected" ? "已驳回" : "待处理";
}

function typeText(t) {
  const map = {
    leave: "请假",
    expense: "报销",
    purchase: "采购",
    overtime: "加班",
    attendance_correction: "补卡/改卡",
    business_trip: "出差",
    outing: "外出",
    travel_expense: "差旅报销",
    onboarding: "入职",
    probation: "转正",
    resignation: "离职",
    job_transfer: "调岗",
    salary_adjustment: "调薪",
    loan: "借款",
    payment: "付款",
    budget: "预算",
    invoice: "开票",
    fixed_asset_accounting: "固定资产入账",
    purchase_plus: "采购（增强）",
    quote_compare: "比价/询价",
    acceptance: "验收",
    inventory_in: "入库",
    inventory_out: "出库",
    device_claim: "设备申领",
    asset_transfer: "资产调拨",
    asset_maintenance: "资产维修",
    asset_scrap: "资产报废",
    contract: "合同审批",
    legal_review: "法务审查",
    seal: "用章申请",
    archive: "归档",
    account_open: "账号开通",
    permission: "系统权限申请",
    vpn_email: "VPN/邮箱开通",
    it_device: "设备申请",
    meeting_room: "会议室预定",
    car: "用车申请",
    supplies: "物品领用",
  };
  return map[t] || "通用";
}

function stepText(step) {
  return step === "manager"
    ? "直属领导审批"
    : step === "gm"
    ? "总经理审批"
    : step === "hr"
    ? "人事审批"
    : step === "legal"
    ? "法务审批"
    : step === "finance"
    ? "财务审批"
    : step === "procurement"
    ? "采购审批"
    : step === "it"
    ? "IT审批"
    : step === "admin"
    ? "行政/管理员审批"
    : "审批";
}

let currentMe = null;
let currentTab = "create";
let workflowItems = [];
let workflowsByKey = {};
let adminWorkflows = [];
let adminRoles = [];

function setTab(tab) {
  currentTab = tab;
  for (const t of ["create", "requests", "inbox", "notifications", "roles", "users", "workflows"]) {
    const el = $(`#tab-${t}`);
    if (el) el.hidden = t !== tab;
  }
  document.querySelectorAll(".tabbtn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  if (tab === "requests") refreshRequests();
  if (tab === "inbox") refreshInbox();
  if (tab === "notifications") refreshNotifications();
  if (tab === "roles") refreshRoles();
  if (tab === "users") refreshUsers();
  if (tab === "workflows") refreshAdminWorkflows();
}

function showCreateFields(type) {
  const map = {
    leave: "leaveFields",
    expense: "expenseFields",
    purchase: "purchaseFields",
    overtime: "overtimeFields",
    attendance_correction: "attendanceFields",
    business_trip: "businessTripFields",
    outing: "outingFields",
    travel_expense: "travelExpenseFields",
    onboarding: "onboardingFields",
    probation: "probationFields",
    resignation: "resignationFields",
    job_transfer: "jobTransferFields",
    salary_adjustment: "salaryAdjustFields",
    loan: "loanFields",
    payment: "paymentFields",
    budget: "budgetFields",
    invoice: "invoiceFields",
    fixed_asset_accounting: "fixedAssetFields",
    purchase_plus: "purchasePlusFields",
    quote_compare: "quoteCompareFields",
    acceptance: "acceptanceFields",
    inventory_in: "inventoryInFields",
    inventory_out: "inventoryOutFields",
    device_claim: "deviceClaimFields",
    asset_transfer: "assetTransferFields",
    asset_maintenance: "assetMaintenanceFields",
    asset_scrap: "assetScrapFields",
    contract: "contractFields",
    legal_review: "legalReviewFields",
    seal: "sealFields",
    archive: "archiveFields",
    account_open: "accountOpenFields",
    permission: "permissionFields",
    vpn_email: "vpnEmailFields",
    it_device: "itDeviceFields",
    meeting_room: "meetingRoomFields",
    car: "carFields",
    supplies: "suppliesFields",
  };
  for (const id of Object.values(map)) {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
  }
  const target = map[type];
  if (target) {
    const el = document.getElementById(target);
    if (el) el.hidden = false;
  }
}

function groupWorkflows(items) {
  const groups = new Map();
  for (const w of items) {
    const cat = w.category || "Other";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(w);
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function optionLabel(w) {
  const scope = w.scope_kind === "dept" ? `部门：${w.scope_value}` : "公司通用";
  return `${w.name}（${scope}）`;
}

async function loadWorkflows() {
  const data = await api("/api/workflows");
  workflowItems = data.items || [];
  workflowsByKey = {};
  for (const w of workflowItems) workflowsByKey[w.key] = w;

  const sel = $("#workflowKey");
  sel.innerHTML = "";
  const groups = groupWorkflows(workflowItems);
  for (const [cat, items] of groups) {
    const og = document.createElement("optgroup");
    og.label = cat;
    for (const w of items) {
      const opt = document.createElement("option");
      opt.value = w.key;
      opt.textContent = optionLabel(w);
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }

  let defaultKey = workflowItems.find((w) => w.is_default)?.key || workflowItems[0]?.key;
  if (defaultKey) sel.value = defaultKey;
  onWorkflowChanged();
}

function onWorkflowChanged() {
  const sel = $("#workflowKey");
  const wf = workflowsByKey[sel.value];
  if (!wf) return;
  $("#workflowHint").textContent = `${wf.category} / ${wf.request_type} / ${wf.key}`;
  showCreateFields(wf.request_type);
}

async function refreshMe() {
  try {
    return await api("/api/me");
  } catch {
    return null;
  }
}

function hasPerm(key) {
  if (!currentMe) return false;
  const perms = currentMe.permissions || [];
  return perms.includes("*") || perms.includes(key);
}

function renderEmpty(listEl, text) {
  listEl.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "muted";
  empty.textContent = text;
  listEl.appendChild(empty);
}

async function refreshRequests() {
  const list = $("#requestsList");
  if (!currentMe) return;
  const scope = currentMe.role === "admin" && $("#scopeAll").checked ? "all" : "mine";
  const data = await api(`/api/requests?scope=${encodeURIComponent(scope)}`);
  renderRequests(list, data.items || []);
}

async function refreshInbox() {
  const list = $("#inboxList");
  if (!currentMe) return;
  const data = await api("/api/inbox");
  renderInbox(list, data.items || []);
}

async function refreshNotifications() {
  const list = $("#notificationsList");
  if (!currentMe) return;
  const data = await api("/api/notifications");
  renderNotifications(list, data.items || []);
}

async function refreshRoles() {
  if (!currentMe || !hasPerm("rbac:manage")) return;
  const data = await api("/api/admin/roles");
  adminRoles = data.items || [];

  const sel = $("#roleSelect");
  sel.innerHTML = "";
  for (const r of adminRoles) {
    const opt = document.createElement("option");
    opt.value = r.role;
    opt.textContent = r.role;
    sel.appendChild(opt);
  }
  if (adminRoles.length) {
    sel.value = adminRoles[0].role;
    loadRole(sel.value);
  } else {
    newRole();
  }
}

function loadRole(roleName) {
  const r = adminRoles.find((x) => x.role === roleName);
  if (!r) return;
  $("#roleName").value = r.role;
  $("#rolePerms").value = (r.permissions || []).join("\n");
  $("#roleMsg").textContent = "";
}

function newRole() {
  $("#roleName").value = "";
  $("#rolePerms").value = "";
  $("#roleMsg").textContent = "新建模式";
}

async function saveRole() {
  $("#roleMsg").textContent = "";
  const role = $("#roleName").value.trim();
  const permissions = $("#rolePerms")
    .value.split(/\r?\n/g)
    .map((s) => s.trim())
    .filter((s) => s);
  if (!role) {
    $("#roleMsg").textContent = "角色名不能为空";
    return;
  }
  try {
    await api("/api/admin/roles", { method: "POST", body: { role, permissions } });
    $("#roleMsg").textContent = "已保存";
    await refreshRoles();
    await refreshUsers();
  } catch (e) {
    $("#roleMsg").textContent = e.code || "保存失败";
  }
}

async function refreshUsers() {
  const list = $("#usersList");
  if (!currentMe || currentMe.role !== "admin") return;
  const data = await api("/api/users");
  renderUsers(list, data.items || []);
}

function renderRequests(list, items) {
  if (!items.length) return renderEmpty(list, "暂无申请");
  list.innerHTML = "";

  for (const item of items) {
    const el = document.createElement("div");
    el.className = "item";

    const top = document.createElement("div");
    top.className = "item-top";

    const sBadge = document.createElement("span");
    sBadge.className = `badge ${badgeClass(item.status)}`;
    sBadge.textContent = statusText(item.status);

    const tBadge = document.createElement("span");
    tBadge.className = "badge";
    tBadge.textContent = typeText(item.type);

    const wfBadge = document.createElement("span");
    wfBadge.className = "badge";
    wfBadge.textContent = item.workflow?.name || item.workflow?.key || "";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = item.title;

    const owner = document.createElement("span");
    owner.className = "badge";
    owner.textContent = `申请人：${item.owner.username}`;

    const spacer = document.createElement("div");
    spacer.className = "spacer";

    const detailBtn = document.createElement("button");
    detailBtn.className = "btn btn-secondary";
    detailBtn.textContent = "详情";

    top.appendChild(sBadge);
    top.appendChild(tBadge);
    if (wfBadge.textContent) top.appendChild(wfBadge);
    top.appendChild(title);
    top.appendChild(owner);
    top.appendChild(spacer);
    top.appendChild(detailBtn);
    el.appendChild(top);

    const body = document.createElement("div");
    body.className = "item-body";
    body.textContent = item.body;
    el.appendChild(body);

    const meta = document.createElement("div");
    meta.className = "item-meta";
    meta.textContent = `创建：${fmtTime(item.created_at)}`;
    if (item.pending_task) {
      const a =
        item.pending_task.assignee_username ||
        (item.pending_task.assignee_role ? `角色：${item.pending_task.assignee_role}` : "-");
      meta.textContent += ` · 当前：${stepText(item.pending_task.step_key)}（${a}）`;
    }
    if (item.decided_at) {
      meta.textContent += ` · 结束：${fmtTime(item.decided_at)}（${item.decided_by?.username || "-"}）`;
    }
    el.appendChild(meta);

    const detailWrap = document.createElement("div");
    detailWrap.className = "item-body";
    detailWrap.style.display = "none";
    detailWrap.style.marginTop = "10px";
    el.appendChild(detailWrap);

    let loaded = false;
    detailBtn.onclick = async () => {
      const open = detailWrap.style.display !== "none";
      detailWrap.style.display = open ? "none" : "block";
      if (open || loaded) return;
      loaded = true;
      try {
        const data = await api(`/api/requests/${item.id}`);
        const tasks = data.tasks || [];
        const events = data.events || [];
        const lines = [];
        const payload = data.request?.payload || null;
        if (payload) {
          lines.push("表单：");
          if (data.request.type === "leave") {
            lines.push(`- 开始：${payload.start_date}`);
            lines.push(`- 结束：${payload.end_date}`);
            lines.push(`- 天数：${payload.days}`);
            lines.push(`- 原因：${payload.reason}`);
          } else if (data.request.type === "expense") {
            lines.push(`- 类别：${payload.category || ""}`);
            lines.push(`- 金额：${payload.amount}`);
            if (payload.reason) lines.push(`- 说明：${payload.reason}`);
          } else if (data.request.type === "purchase") {
            lines.push(`- 金额：${payload.amount}`);
            if (payload.items?.length) {
              for (const it of payload.items) {
                lines.push(`- 物品：${it.name} ×${it.qty} 单价${it.unit_price} 小计${it.line_total}`);
              }
            }
            if (payload.reason) lines.push(`- 原因：${payload.reason}`);
          }
          lines.push("");
        }
        lines.push("流程：");
        for (const t of tasks) {
          lines.push(
            `- ${stepText(t.step_key)}：${t.status}${
              t.decided_at ? `（${fmtTime(t.decided_at)} ${t.decided_by_username || ""}）` : ""
            }${t.comment ? ` · ${t.comment}` : ""}`
          );
        }
        if (events.length) {
          lines.push("");
          lines.push("事件：");
          for (const e of events) {
            const who = e.actor_username || "系统";
            lines.push(`- ${fmtTime(e.created_at)} ${who} ${e.event_type}${e.message ? ` · ${e.message}` : ""}`);
          }
        }
        detailWrap.textContent = lines.join("\n");
      } catch (e) {
        detailWrap.textContent = e.code || "加载失败";
      }
    };

    list.appendChild(el);
  }
}

function renderInbox(list, items) {
  if (!items.length) return renderEmpty(list, "暂无待办");
  list.innerHTML = "";

  for (const it of items) {
    const task = it.task;
    const req = it.request;

    const el = document.createElement("div");
    el.className = "item";

    const top = document.createElement("div");
    top.className = "item-top";

    const badge = document.createElement("span");
    badge.className = "badge pending";
    badge.textContent = "待处理";

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = `${typeText(req.type)} · ${req.title}`;

    const owner = document.createElement("span");
    owner.className = "badge";
    owner.textContent = `申请人：${req.owner_username}`;

    top.appendChild(badge);
    top.appendChild(title);
    top.appendChild(owner);
    el.appendChild(top);

    const body = document.createElement("div");
    body.className = "item-body";
    body.textContent = req.body;
    el.appendChild(body);

    const meta = document.createElement("div");
    meta.className = "item-meta";
    meta.textContent = `步骤：${stepText(task.step_key)} · 创建：${fmtTime(req.created_at)}`;
    el.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "row";
    actions.style.marginTop = "10px";

    const approveBtn = document.createElement("button");
    approveBtn.className = "btn";
    approveBtn.textContent = "通过";

    const rejectBtn = document.createElement("button");
    rejectBtn.className = "btn btn-secondary";
    rejectBtn.textContent = "驳回";

    approveBtn.onclick = async () => {
      approveBtn.disabled = true;
      rejectBtn.disabled = true;
      try {
        const comment = prompt("审批意见（可选）", "") || "";
        await api(`/api/tasks/${task.id}/approve`, { method: "POST", body: comment ? { comment } : {} });
        await refreshInbox();
        await refreshRequests();
      } catch (e) {
        alert(e.code || "审批失败");
      } finally {
        approveBtn.disabled = false;
        rejectBtn.disabled = false;
      }
    };

    rejectBtn.onclick = async () => {
      rejectBtn.disabled = true;
      approveBtn.disabled = true;
      try {
        const comment = prompt("驳回原因（可选）", "") || "";
        await api(`/api/tasks/${task.id}/reject`, { method: "POST", body: comment ? { comment } : {} });
        await refreshInbox();
        await refreshRequests();
      } catch (e) {
        alert(e.code || "驳回失败");
      } finally {
        rejectBtn.disabled = false;
        approveBtn.disabled = false;
      }
    };

    actions.appendChild(approveBtn);
    actions.appendChild(rejectBtn);
    el.appendChild(actions);

    list.appendChild(el);
  }
}

function renderNotifications(list, items) {
  if (!items.length) return renderEmpty(list, "暂无通知");
  list.innerHTML = "";

  for (const n of items) {
    const el = document.createElement("div");
    el.className = "item";

    const top = document.createElement("div");
    top.className = "item-top";

    const badge = document.createElement("span");
    badge.className = `badge ${n.read_at ? "" : "pending"}`.trim();
    badge.textContent = n.read_at ? "已读" : "未读";

    const title = document.createElement("div");
    title.className = "item-title";
    const rid = n.request_id ? `#${n.request_id}` : "";
    const who = n.actor_username ? `（${n.actor_username}）` : "";
    title.textContent = `${n.event_type}${who} ${rid}`.trim();

    const spacer = document.createElement("div");
    spacer.className = "spacer";

    const readBtn = document.createElement("button");
    readBtn.className = "btn btn-secondary";
    readBtn.textContent = "标记已读";
    readBtn.hidden = !!n.read_at;

    readBtn.onclick = async () => {
      readBtn.disabled = true;
      try {
        await api(`/api/notifications/${n.id}/read`, { method: "POST", body: {} });
        await refreshNotifications();
      } catch {
        readBtn.disabled = false;
      }
    };

    top.appendChild(badge);
    top.appendChild(title);
    top.appendChild(spacer);
    top.appendChild(readBtn);
    el.appendChild(top);

    const body = document.createElement("div");
    body.className = "item-body";
    body.textContent = n.message || "";
    el.appendChild(body);

    const meta = document.createElement("div");
    meta.className = "item-meta";
    meta.textContent = `时间：${fmtTime(n.created_at)}`;
    el.appendChild(meta);

    list.appendChild(el);
  }
}

function renderUsers(list, items) {
  if (!items.length) return renderEmpty(list, "暂无用户");
  list.innerHTML = "";

  const options = [
    { id: "", label: "（无）" },
    ...items.map((u) => ({ id: String(u.id), label: `${u.username}（${u.role}）` })),
  ];

  for (const u of items) {
    const el = document.createElement("div");
    el.className = "item";

    const top = document.createElement("div");
    top.className = "item-top";

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = u.role;

    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = u.username;

    top.appendChild(badge);
    top.appendChild(title);
    el.appendChild(top);

    const form = document.createElement("div");
    form.className = "grid";
    form.style.marginTop = "10px";

    const deptLabel = document.createElement("label");
    deptLabel.innerHTML = `<div class="label">部门</div>`;
    const deptInput = document.createElement("input");
    deptInput.value = u.dept || "";
    deptLabel.appendChild(deptInput);

    const mgrLabel = document.createElement("label");
    mgrLabel.innerHTML = `<div class="label">直属领导</div>`;
    const mgrSelect = document.createElement("select");
    for (const o of options) {
      const opt = document.createElement("option");
      opt.value = o.id;
      opt.textContent = o.label;
      mgrSelect.appendChild(opt);
    }
    mgrSelect.value = u.manager_id == null ? "" : String(u.manager_id);
    mgrLabel.appendChild(mgrSelect);

    const row = document.createElement("div");
    row.className = "row";

    const saveBtn = document.createElement("button");
    saveBtn.className = "btn";
    saveBtn.textContent = "保存";

    const msg = document.createElement("div");
    msg.className = "muted";
    msg.style.fontSize = "13px";

    saveBtn.onclick = async () => {
      saveBtn.disabled = true;
      msg.textContent = "";
      try {
        const dept = deptInput.value.trim();
        const manager_id = mgrSelect.value ? Number(mgrSelect.value) : null;
        await api(`/api/users/${u.id}`, { method: "POST", body: { dept, manager_id } });
        msg.textContent = "已保存";
      } catch (e) {
        msg.textContent = e.code || "保存失败";
      } finally {
        saveBtn.disabled = false;
      }
    };

    row.appendChild(saveBtn);
    row.appendChild(msg);

    form.appendChild(deptLabel);
    form.appendChild(mgrLabel);
    form.appendChild(row);
    el.appendChild(form);

    list.appendChild(el);
  }
}

async function refreshAdminWorkflows() {
  if (!currentMe || currentMe.role !== "admin") return;
  const data = await api("/api/admin/workflows");
  adminWorkflows = data.items || [];
  const sel = $("#adminWorkflowSelect");
  sel.innerHTML = "";
  for (const w of adminWorkflows) {
    const opt = document.createElement("option");
    opt.value = w.key;
    const scope = w.scope_kind === "dept" ? `dept:${w.scope_value}` : "global";
    opt.textContent = `${w.category} / ${w.request_type} / ${w.name} (${scope})`;
    sel.appendChild(opt);
  }
  if (adminWorkflows.length) {
    sel.value = adminWorkflows[0].key;
    await loadAdminWorkflow(sel.value);
  } else {
    newWorkflow();
  }
}

function newWorkflow() {
  $("#wfKey").value = "";
  $("#wfType").value = "";
  $("#wfName").value = "";
  $("#wfCategory").value = "";
  $("#wfScopeKind").value = "global";
  $("#wfScopeValue").value = "";
  $("#wfEnabled").checked = true;
  $("#wfDefault").checked = false;
  $("#wfSteps").value = JSON.stringify(
    [{ step_order: 1, step_key: "admin", assignee_kind: "role", assignee_value: "admin" }],
    null,
    2
  );
  $("#wfMsg").textContent = "新建模式";
}

async function loadAdminWorkflow(key) {
  if (!key) return;
  const data = await api(`/api/admin/workflows/${encodeURIComponent(key)}`);
  const wf = data.workflow;
  $("#wfKey").value = wf.key;
  $("#wfType").value = wf.request_type;
  $("#wfName").value = wf.name;
  $("#wfCategory").value = wf.category;
  $("#wfScopeKind").value = wf.scope_kind;
  $("#wfScopeValue").value = wf.scope_value || "";
  $("#wfEnabled").checked = !!wf.enabled;
  $("#wfDefault").checked = !!wf.is_default;
  $("#wfSteps").value = JSON.stringify(data.steps || [], null, 2);
  $("#wfMsg").textContent = "";
}

async function saveAdminWorkflow() {
  $("#wfMsg").textContent = "";
  const workflow_key = $("#wfKey").value.trim();
  const request_type = $("#wfType").value.trim();
  const name = $("#wfName").value.trim();
  const category = $("#wfCategory").value.trim() || "General";
  const scope_kind = $("#wfScopeKind").value;
  const scope_value = $("#wfScopeValue").value.trim() || null;
  const enabled = $("#wfEnabled").checked;
  const is_default = $("#wfDefault").checked;
  let steps;
  try {
    steps = JSON.parse($("#wfSteps").value || "[]");
    if (!Array.isArray(steps)) throw new Error("steps_not_array");
  } catch (e) {
    $("#wfMsg").textContent = "步骤 JSON 无效";
    return;
  }
  try {
    await api("/api/admin/workflows", {
      method: "POST",
      body: { workflow_key, request_type, name, category, scope_kind, scope_value, enabled, is_default, steps },
    });
    $("#wfMsg").textContent = "已保存";
    await refreshAdminWorkflows();
    await loadWorkflows();
  } catch (e) {
    $("#wfMsg").textContent = e.code || "保存失败";
  }
}

async function deleteAdminWorkflow() {
  const workflow_key = $("#wfKey").value.trim();
  if (!workflow_key) return;
  if (!confirm(`确认删除 ${workflow_key} ?`)) return;
  try {
    await api("/api/admin/workflows/delete", { method: "POST", body: { workflow_key } });
    $("#wfMsg").textContent = "已删除";
    await refreshAdminWorkflows();
    await loadWorkflows();
  } catch (e) {
    $("#wfMsg").textContent = e.code || "删除失败";
  }
}

async function refreshAll() {
  currentMe = await refreshMe();
  if (!currentMe) {
    $("#loginView").hidden = false;
    $("#appView").hidden = true;
    $("#logoutBtn").hidden = true;
    $("#whoami").textContent = "";
    return;
  }

  $("#loginView").hidden = true;
  $("#appView").hidden = false;
  $("#logoutBtn").hidden = false;
  $("#whoami").textContent = `当前：${currentMe.username}（${currentMe.role}）`;

  $("#usersTabBtn").hidden = !hasPerm("users:manage");
  $("#rolesTabBtn").hidden = !hasPerm("rbac:manage");
  $("#scopeWrap").hidden = !hasPerm("requests:read_all");
  $("#workflowsTabBtn").hidden = !hasPerm("workflows:manage");

  if (!workflowItems.length) {
    await loadWorkflows().catch(() => {});
  }
  setTab(currentTab);
}

document.querySelectorAll(".tabbtn").forEach((b) => {
  b.onclick = () => setTab(b.dataset.tab);
});

$("#loginBtn").onclick = async () => {
  setError($("#loginError"), "");
  const username = $("#username").value.trim();
  const password = $("#password").value;
  try {
    await api("/api/login", { method: "POST", body: { username, password } });
    $("#password").value = "";
    currentTab = "requests";
    await refreshAll();
  } catch (e) {
    setError($("#loginError"), e.code === "invalid_credentials" ? "用户名或密码错误" : e.code);
  }
};

$("#logoutBtn").onclick = async () => {
  await api("/api/logout", { method: "POST" }).catch(() => {});
  await refreshAll();
};

$("#refreshRequestsBtn").onclick = refreshRequests;
$("#refreshInboxBtn").onclick = refreshInbox;
$("#refreshNotificationsBtn").onclick = refreshNotifications;
$("#refreshRolesBtn").onclick = refreshRoles;
$("#refreshUsersBtn").onclick = refreshUsers;
$("#refreshWorkflowsBtn").onclick = refreshAdminWorkflows;
$("#scopeAll").onchange = refreshRequests;

$("#workflowKey").onchange = onWorkflowChanged;

// Admin role editor events
$("#roleSelect").onchange = () => loadRole($("#roleSelect").value);
$("#newRoleBtn").onclick = newRole;
$("#saveRoleBtn").onclick = saveRole;

$("#createBtn").onclick = async () => {
  setError($("#createError"), "");
  const wfKey = $("#workflowKey").value;
  const wf = workflowsByKey[wfKey];
  const type = wf?.request_type || "generic";
  let title = $("#reqTitle").value.trim();
  let body = $("#reqBody").value.trim();
  let payload = null;

  if (type === "leave") {
    const start_date = $("#leaveStart").value;
    const end_date = $("#leaveEnd").value;
    const days = Number($("#leaveDays").value || 0);
    const reason = $("#leaveReason").value.trim();
    if (!start_date || !end_date || !days || !reason) {
      setError($("#createError"), "请假需要填写开始/结束/天数/原因");
      return;
    }
    payload = { start_date, end_date, days, reason };
    title = title || "";
    body = body || "";
  } else if (type === "expense") {
    const category = $("#expenseCategory").value.trim();
    const amount = Number($("#expenseAmount").value || 0);
    const reason = $("#expenseReason").value.trim();
    if (!amount || amount <= 0) {
      setError($("#createError"), "报销金额必须大于 0");
      return;
    }
    payload = { category, amount, reason };
    title = title || "";
    body = body || "";
  } else if (type === "purchase") {
    const name = $("#purchaseItemName").value.trim();
    const qty = Number($("#purchaseQty").value || 0);
    const unit_price = Number($("#purchaseUnitPrice").value || 0);
    const reason = $("#purchaseReason").value.trim();
    if (!name || !qty || qty <= 0 || !unit_price || unit_price <= 0 || !reason) {
      setError($("#createError"), "采购需要填写物品名称/数量/单价/原因");
      return;
    }
    const amount = qty * unit_price;
    payload = { items: [{ name, qty, unit_price }], reason, amount };
    title = title || "";
    body = body || "";
  } else if (type === "overtime") {
    const date = $("#overtimeDate").value;
    const hours = Number($("#overtimeHours").value || 0);
    const reason = $("#overtimeReason").value.trim();
    if (!date || !hours || hours <= 0 || !reason) {
      setError($("#createError"), "加班需要填写日期/时长/原因");
      return;
    }
    payload = { date, hours, reason };
    title = title || "";
    body = body || "";
  } else if (type === "attendance_correction") {
    const date = $("#attDate").value;
    const kind = $("#attKind").value;
    const time = $("#attTime").value;
    const reason = $("#attReason").value.trim();
    if (!date || !kind || !time || !reason) {
      setError($("#createError"), "补卡需要填写日期/类型/时间/原因");
      return;
    }
    payload = { date, kind, time, reason };
    title = title || "";
    body = body || "";
  } else if (type === "business_trip") {
    const start_date = $("#tripStart").value;
    const end_date = $("#tripEnd").value;
    const destination = $("#tripDestination").value.trim();
    const purpose = $("#tripPurpose").value.trim();
    if (!start_date || !end_date || !destination || !purpose) {
      setError($("#createError"), "出差需要填写开始/结束/目的地/事由");
      return;
    }
    payload = { start_date, end_date, destination, purpose };
    title = title || "";
    body = body || "";
  } else if (type === "outing") {
    const date = $("#outingDate").value;
    const start_time = $("#outingStart").value;
    const end_time = $("#outingEnd").value;
    const destination = $("#outingDestination").value.trim();
    const reason = $("#outingReason").value.trim();
    if (!date || !start_time || !end_time || !destination || !reason) {
      setError($("#createError"), "外出需要填写日期/开始/结束/地点/原因");
      return;
    }
    payload = { date, start_time, end_time, destination, reason };
    title = title || "";
    body = body || "";
  } else if (type === "travel_expense") {
    const start_date = $("#travelStart").value;
    const end_date = $("#travelEnd").value;
    const amount = Number($("#travelAmount").value || 0);
    const reason = $("#travelReason").value.trim();
    if (!start_date || !end_date || !amount || amount <= 0) {
      setError($("#createError"), "差旅报销需要填写开始/结束/金额");
      return;
    }
    payload = { start_date, end_date, amount, reason };
    title = title || "";
    body = body || "";
  } else if (type === "onboarding") {
    const name = $("#onboardName").value.trim();
    const start_date = $("#onboardDate").value;
    const dept = $("#onboardDept").value.trim();
    const position = $("#onboardPosition").value.trim();
    if (!name || !start_date || !dept || !position) {
      setError($("#createError"), "入职需要填写姓名/日期/部门/岗位");
      return;
    }
    payload = { name, start_date, dept, position };
    title = title || "";
    body = body || "";
  } else if (type === "probation") {
    const name = $("#probName").value.trim();
    const start_date = $("#probStart").value;
    const end_date = $("#probEnd").value;
    const result = $("#probResult").value;
    const comment = $("#probComment").value.trim();
    if (!name || !start_date || !end_date || !result) {
      setError($("#createError"), "转正需要填写姓名/开始/结束/结果");
      return;
    }
    payload = { name, start_date, end_date, result, comment };
    title = title || "";
    body = body || "";
  } else if (type === "resignation") {
    const name = $("#resignName").value.trim();
    const last_day = $("#resignLastDay").value;
    const reason = $("#resignReason").value.trim();
    const handover = $("#resignHandover").value.trim();
    if (!name || !last_day || !reason) {
      setError($("#createError"), "离职需要填写姓名/最后工作日/离职原因");
      return;
    }
    payload = { name, last_day, reason, handover };
    title = title || "";
    body = body || "";
  } else if (type === "job_transfer") {
    const name = $("#transferName").value.trim();
    const from_dept = $("#transferFrom").value.trim();
    const to_dept = $("#transferTo").value.trim();
    const effective_date = $("#transferDate").value;
    const reason = $("#transferReason").value.trim();
    if (!name || !from_dept || !to_dept || !effective_date) {
      setError($("#createError"), "调岗需要填写姓名/原部门/新部门/生效日期");
      return;
    }
    payload = { name, from_dept, to_dept, effective_date, reason };
    title = title || "";
    body = body || "";
  } else if (type === "salary_adjustment") {
    const name = $("#salaryName").value.trim();
    const effective_date = $("#salaryDate").value;
    const from_salary = Number($("#salaryFrom").value || 0);
    const to_salary = Number($("#salaryTo").value || 0);
    const reason = $("#salaryReason").value.trim();
    if (!name || !effective_date || !from_salary || from_salary <= 0 || !to_salary || to_salary <= 0) {
      setError($("#createError"), "调薪需要填写姓名/生效日期/原薪资/新薪资");
      return;
    }
    payload = { name, effective_date, from_salary, to_salary, reason };
    title = title || "";
    body = body || "";
  } else if (type === "loan") {
    const amount = Number($("#loanAmount").value || 0);
    const reason = $("#loanReason").value.trim();
    if (!amount || amount <= 0 || !reason) {
      setError($("#createError"), "借款需要填写金额/用途");
      return;
    }
    payload = { amount, reason };
    title = title || "";
    body = body || "";
  } else if (type === "payment") {
    const payee = $("#paymentPayee").value.trim();
    const amount = Number($("#paymentAmount").value || 0);
    const purpose = $("#paymentPurpose").value.trim();
    if (!payee || !amount || amount <= 0 || !purpose) {
      setError($("#createError"), "付款需要填写收款方/金额/用途");
      return;
    }
    payload = { payee, amount, purpose };
    title = title || "";
    body = body || "";
  } else if (type === "budget") {
    const dept = $("#budgetDept").value.trim();
    const period = $("#budgetPeriod").value.trim();
    const amount = Number($("#budgetAmount").value || 0);
    const purpose = $("#budgetPurpose").value.trim();
    if (!dept || !period || !amount || amount <= 0 || !purpose) {
      setError($("#createError"), "预算需要填写部门/期间/金额/用途");
      return;
    }
    payload = { dept, period, amount, purpose };
    title = title || "";
    body = body || "";
  } else if (type === "invoice") {
    const invoiceTitle = $("#invoiceTitle").value.trim();
    const amount = Number($("#invoiceAmount").value || 0);
    const purpose = $("#invoicePurpose").value.trim();
    if (!invoiceTitle || !amount || amount <= 0 || !purpose) {
      setError($("#createError"), "开票需要填写抬头/金额/用途");
      return;
    }
    payload = { title: invoiceTitle, amount, purpose };
    title = title || "";
    body = body || "";
  } else if (type === "fixed_asset_accounting") {
    const asset_name = $("#faName").value.trim();
    const amount = Number($("#faAmount").value || 0);
    const acquired_date = $("#faDate").value;
    if (!asset_name || !amount || amount <= 0 || !acquired_date) {
      setError($("#createError"), "固定资产入账需要填写资产名称/金额/购置日期");
      return;
    }
    payload = { asset_name, amount, acquired_date };
    title = title || "";
    body = body || "";
  } else if (type === "purchase_plus") {
    const name = $("#ppItemName").value.trim();
    const qty = Number($("#ppQty").value || 0);
    const unit_price = Number($("#ppUnitPrice").value || 0);
    const vendor = $("#ppVendor").value.trim();
    const delivery_date = $("#ppDeliveryDate").value;
    const reason = $("#ppReason").value.trim();
    if (!name || !qty || qty <= 0 || !unit_price || unit_price <= 0 || !vendor || !delivery_date || !reason) {
      setError($("#createError"), "采购（增强）需要填写物品/数量/单价/供应商/交付日期/原因");
      return;
    }
    payload = { items: [{ name, qty, unit_price }], vendor, delivery_date, reason };
    title = title || "";
    body = body || "";
  } else if (type === "quote_compare") {
    const subject = $("#qcSubject").value.trim();
    const vendors = $("#qcVendors")
      .value.split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const recommendation = $("#qcRecommendation").value.trim();
    if (!subject || vendors.length < 2 || !recommendation) {
      setError($("#createError"), "比价需要填写主题/至少2个供应商/推荐结论");
      return;
    }
    payload = { subject, vendors, recommendation };
    title = title || "";
    body = body || "";
  } else if (type === "acceptance") {
    const purchase_ref = $("#accPurchaseRef").value.trim();
    const acceptance_date = $("#accDate").value;
    const summary = $("#accSummary").value.trim();
    if (!purchase_ref || !acceptance_date || !summary) {
      setError($("#createError"), "验收需要填写采购单号/验收日期/验收说明");
      return;
    }
    payload = { purchase_ref, acceptance_date, summary };
    title = title || "";
    body = body || "";
  } else if (type === "inventory_in") {
    const warehouse = $("#invInWarehouse").value.trim();
    const date = $("#invInDate").value;
    const name = $("#invInItem").value.trim();
    const qty = Number($("#invInQty").value || 0);
    if (!warehouse || !date || !name || !qty || qty <= 0) {
      setError($("#createError"), "入库需要填写仓库/日期/物品/数量");
      return;
    }
    payload = { warehouse, date, items: [{ name, qty }] };
    title = title || "";
    body = body || "";
  } else if (type === "inventory_out") {
    const warehouse = $("#invOutWarehouse").value.trim();
    const date = $("#invOutDate").value;
    const name = $("#invOutItem").value.trim();
    const qty = Number($("#invOutQty").value || 0);
    const reason = $("#invOutReason").value.trim();
    if (!warehouse || !date || !name || !qty || qty <= 0 || !reason) {
      setError($("#createError"), "出库需要填写仓库/日期/物品/数量/原因");
      return;
    }
    payload = { warehouse, date, items: [{ name, qty }], reason };
    title = title || "";
    body = body || "";
  } else if (type === "device_claim") {
    const item = $("#dcItem").value.trim();
    const qty = Number($("#dcQty").value || 0);
    const reason = $("#dcReason").value.trim();
    if (!item || !qty || qty <= 0 || !reason) {
      setError($("#createError"), "设备申领需要填写物品/数量/原因");
      return;
    }
    payload = { item, qty, reason };
    title = title || "";
    body = body || "";
  } else if (type === "asset_transfer") {
    const asset = $("#atAsset").value.trim();
    const from_user = $("#atFromUser").value.trim();
    const to_user = $("#atToUser").value.trim();
    const date = $("#atDate").value;
    if (!asset || !from_user || !to_user || !date) {
      setError($("#createError"), "资产调拨需要填写资产标识/原使用人/新使用人/日期");
      return;
    }
    payload = { asset, from_user, to_user, date };
    title = title || "";
    body = body || "";
  } else if (type === "asset_maintenance") {
    const asset = $("#amAsset").value.trim();
    const issue = $("#amIssue").value.trim();
    const amount = Number($("#amAmount").value || 0);
    if (!asset || !issue || amount < 0) {
      setError($("#createError"), "资产维修需要填写资产标识/问题描述（费用可选）");
      return;
    }
    payload = { asset, issue, amount };
    title = title || "";
    body = body || "";
  } else if (type === "asset_scrap") {
    const asset = $("#asAsset").value.trim();
    const scrap_date = $("#asDate").value;
    const reason = $("#asReason").value.trim();
    const amount = Number($("#asAmount").value || 0);
    if (!asset || !scrap_date || !reason || amount < 0) {
      setError($("#createError"), "资产报废需要填写资产标识/报废日期/原因（残值可选）");
      return;
    }
    payload = { asset, scrap_date, reason, amount };
    title = title || "";
    body = body || "";
  } else if (type === "contract") {
    const name = $("#contractName").value.trim();
    const party = $("#contractParty").value.trim();
    const amount = Number($("#contractAmount").value || 0);
    const start_date = $("#contractStart").value;
    const end_date = $("#contractEnd").value;
    const summary = $("#contractSummary").value.trim();
    if (!name || !party || !amount || amount <= 0 || !start_date || !end_date) {
      setError($("#createError"), "合同审批需要填写合同名称/对方/金额/开始/结束");
      return;
    }
    payload = { name, party, amount, start_date, end_date, summary };
    title = title || "";
    body = body || "";
  } else if (type === "legal_review") {
    const subject = $("#legalSubject").value.trim();
    const risk_level = $("#legalRisk").value;
    const notes = $("#legalNotes").value.trim();
    if (!subject || !risk_level) {
      setError($("#createError"), "法务审查需要填写主题/风险等级");
      return;
    }
    payload = { subject, risk_level, notes };
    title = title || "";
    body = body || "";
  } else if (type === "seal") {
    const document = $("#sealDocument").value.trim();
    const seal_type = $("#sealType").value;
    const purpose = $("#sealPurpose").value.trim();
    const needed_date = $("#sealNeeded").value;
    if (!document || !seal_type || !purpose || !needed_date) {
      setError($("#createError"), "用章需要填写文件/类型/用途/日期");
      return;
    }
    payload = { document, seal_type, purpose, needed_date };
    title = title || "";
    body = body || "";
  } else if (type === "archive") {
    const document = $("#archiveDocument").value.trim();
    const archive_type = $("#archiveType").value.trim();
    const retention_years = Number($("#archiveYears").value || 0);
    if (!document || !archive_type || !retention_years || retention_years <= 0) {
      setError($("#createError"), "归档需要填写文件/类型/年限");
      return;
    }
    payload = { document, archive_type, retention_years };
    title = title || "";
    body = body || "";
  } else if (type === "account_open") {
    const system = $("#aoSystem").value.trim();
    const account = $("#aoAccount").value.trim();
    const dept = $("#aoDept").value.trim();
    const reason = $("#aoReason").value.trim();
    if (!system || !account || !dept || !reason) {
      setError($("#createError"), "账号开通需要填写系统/账号/部门/原因");
      return;
    }
    payload = { system, account, dept, reason };
    title = title || "";
    body = body || "";
  } else if (type === "permission") {
    const system = $("#permSystem").value.trim();
    const permission = $("#permValue").value.trim();
    const duration_days = Number($("#permDays").value || 0);
    const reason = $("#permReason").value.trim();
    if (!system || !permission || !duration_days || duration_days <= 0 || !reason) {
      setError($("#createError"), "权限申请需要填写系统/权限/期限/原因");
      return;
    }
    payload = { system, permission, duration_days, reason };
    title = title || "";
    body = body || "";
  } else if (type === "vpn_email") {
    const kind = $("#veKind").value;
    const account = $("#veAccount").value.trim();
    const reason = $("#veReason").value.trim();
    if (!kind || !account || !reason) {
      setError($("#createError"), "VPN/邮箱开通需要填写类型/账号/原因");
      return;
    }
    payload = { kind, account, reason };
    title = title || "";
    body = body || "";
  } else if (type === "it_device") {
    const item = $("#itDevItem").value.trim();
    const qty = Number($("#itDevQty").value || 0);
    const reason = $("#itDevReason").value.trim();
    if (!item || !qty || qty <= 0 || !reason) {
      setError($("#createError"), "设备申请需要填写设备/数量/原因");
      return;
    }
    payload = { item, qty, reason };
    title = title || "";
    body = body || "";
  } else if (type === "meeting_room") {
    const room = $("#mrRoom").value.trim();
    const date = $("#mrDate").value;
    const start_time = $("#mrStart").value;
    const end_time = $("#mrEnd").value;
    const subject = $("#mrSubject").value.trim();
    if (!room || !date || !start_time || !end_time || !subject) {
      setError($("#createError"), "会议室预定需要填写会议室/日期/开始/结束/主题");
      return;
    }
    payload = { room, date, start_time, end_time, subject };
    title = title || "";
    body = body || "";
  } else if (type === "car") {
    const date = $("#carDate").value;
    const start_time = $("#carStart").value;
    const end_time = $("#carEnd").value;
    const from = $("#carFrom").value.trim();
    const to = $("#carTo").value.trim();
    const reason = $("#carReason").value.trim();
    if (!date || !start_time || !end_time || !from || !to || !reason) {
      setError($("#createError"), "用车需要填写日期/开始/结束/出发地/目的地/原因");
      return;
    }
    payload = { date, start_time, end_time, from, to, reason };
    title = title || "";
    body = body || "";
  } else if (type === "supplies") {
    const name = $("#supItem").value.trim();
    const qty = Number($("#supQty").value || 0);
    const reason = $("#supReason").value.trim();
    if (!name || !qty || qty <= 0 || !reason) {
      setError($("#createError"), "物品领用需要填写物品/数量/原因");
      return;
    }
    payload = { items: [{ name, qty }], reason };
    title = title || "";
    body = body || "";
  } else {
    if (!title || !body) {
      setError($("#createError"), "标题和内容不能为空");
      return;
    }
  }

  try {
    const created = await api("/api/requests", { method: "POST", body: { workflow: wfKey, type, title, body, payload } });
    const file = $("#attachFile").files && $("#attachFile").files[0];
    if (file) {
      const content_base64 = await readFileAsBase64(file);
      await api(`/api/requests/${created.id}/attachments`, {
        method: "POST",
        body: {
          filename: file.name,
          content_type: file.type || "application/octet-stream",
          content_base64,
        },
      });
    }
    $("#reqTitle").value = "";
    $("#reqBody").value = "";
    $("#attachFile").value = "";
    $("#leaveReason").value = "";
    $("#leaveDays").value = "";
    $("#expenseCategory").value = "";
    $("#expenseAmount").value = "";
    $("#expenseReason").value = "";
    $("#purchaseItemName").value = "";
    $("#purchaseQty").value = "";
    $("#purchaseUnitPrice").value = "";
    $("#purchaseReason").value = "";
    $("#overtimeDate").value = "";
    $("#overtimeHours").value = "";
    $("#overtimeReason").value = "";
    $("#attDate").value = "";
    $("#attKind").value = "in";
    $("#attTime").value = "";
    $("#attReason").value = "";
    $("#tripStart").value = "";
    $("#tripEnd").value = "";
    $("#tripDestination").value = "";
    $("#tripPurpose").value = "";
    $("#outingDate").value = "";
    $("#outingStart").value = "";
    $("#outingEnd").value = "";
    $("#outingDestination").value = "";
    $("#outingReason").value = "";
    $("#travelStart").value = "";
    $("#travelEnd").value = "";
    $("#travelAmount").value = "";
    $("#travelReason").value = "";
    $("#onboardName").value = "";
    $("#onboardDate").value = "";
    $("#onboardDept").value = "";
    $("#onboardPosition").value = "";
    $("#probName").value = "";
    $("#probStart").value = "";
    $("#probEnd").value = "";
    $("#probResult").value = "pass";
    $("#probComment").value = "";
    $("#resignName").value = "";
    $("#resignLastDay").value = "";
    $("#resignReason").value = "";
    $("#resignHandover").value = "";
    $("#transferName").value = "";
    $("#transferFrom").value = "";
    $("#transferTo").value = "";
    $("#transferDate").value = "";
    $("#transferReason").value = "";
    $("#salaryName").value = "";
    $("#salaryDate").value = "";
    $("#salaryFrom").value = "";
    $("#salaryTo").value = "";
    $("#salaryReason").value = "";
    $("#loanAmount").value = "";
    $("#loanReason").value = "";
    $("#paymentPayee").value = "";
    $("#paymentAmount").value = "";
    $("#paymentPurpose").value = "";
    $("#budgetDept").value = "";
    $("#budgetPeriod").value = "";
    $("#budgetAmount").value = "";
    $("#budgetPurpose").value = "";
    $("#invoiceTitle").value = "";
    $("#invoiceAmount").value = "";
    $("#invoicePurpose").value = "";
    $("#faName").value = "";
    $("#faAmount").value = "";
    $("#faDate").value = "";
    $("#ppItemName").value = "";
    $("#ppQty").value = "";
    $("#ppUnitPrice").value = "";
    $("#ppVendor").value = "";
    $("#ppDeliveryDate").value = "";
    $("#ppReason").value = "";
    $("#qcSubject").value = "";
    $("#qcVendors").value = "";
    $("#qcRecommendation").value = "";
    $("#accPurchaseRef").value = "";
    $("#accDate").value = "";
    $("#accSummary").value = "";
    $("#invInWarehouse").value = "";
    $("#invInDate").value = "";
    $("#invInItem").value = "";
    $("#invInQty").value = "";
    $("#invOutWarehouse").value = "";
    $("#invOutDate").value = "";
    $("#invOutItem").value = "";
    $("#invOutQty").value = "";
    $("#invOutReason").value = "";
    $("#dcItem").value = "";
    $("#dcQty").value = "";
    $("#dcReason").value = "";
    $("#atAsset").value = "";
    $("#atFromUser").value = "";
    $("#atToUser").value = "";
    $("#atDate").value = "";
    $("#amAsset").value = "";
    $("#amIssue").value = "";
    $("#amAmount").value = "";
    $("#asAsset").value = "";
    $("#asDate").value = "";
    $("#asAmount").value = "";
    $("#asReason").value = "";
    $("#contractName").value = "";
    $("#contractParty").value = "";
    $("#contractAmount").value = "";
    $("#contractStart").value = "";
    $("#contractEnd").value = "";
    $("#contractSummary").value = "";
    $("#legalSubject").value = "";
    $("#legalRisk").value = "medium";
    $("#legalNotes").value = "";
    $("#sealDocument").value = "";
    $("#sealType").value = "公章";
    $("#sealNeeded").value = "";
    $("#sealPurpose").value = "";
    $("#archiveDocument").value = "";
    $("#archiveType").value = "";
    $("#archiveYears").value = "";
    $("#aoSystem").value = "";
    $("#aoAccount").value = "";
    $("#aoDept").value = "";
    $("#aoReason").value = "";
    $("#permSystem").value = "";
    $("#permValue").value = "";
    $("#permDays").value = "";
    $("#permReason").value = "";
    $("#veKind").value = "vpn";
    $("#veAccount").value = "";
    $("#veReason").value = "";
    $("#itDevItem").value = "";
    $("#itDevQty").value = "";
    $("#itDevReason").value = "";
    $("#mrRoom").value = "";
    $("#mrDate").value = "";
    $("#mrStart").value = "";
    $("#mrEnd").value = "";
    $("#mrSubject").value = "";
    $("#carDate").value = "";
    $("#carStart").value = "";
    $("#carEnd").value = "";
    $("#carFrom").value = "";
    $("#carTo").value = "";
    $("#carReason").value = "";
    $("#supItem").value = "";
    $("#supQty").value = "";
    $("#supReason").value = "";
    currentTab = "requests";
    setTab("requests");
  } catch (e) {
    setError($("#createError"), e.code || "提交失败");
  }
};

refreshAll();

// Admin workflow editor events
$("#adminWorkflowSelect").onchange = async () => loadAdminWorkflow($("#adminWorkflowSelect").value);
$("#newWorkflowBtn").onclick = newWorkflow;
$("#saveWorkflowBtn").onclick = saveAdminWorkflow;
$("#deleteWorkflowBtn").onclick = deleteAdminWorkflow;
