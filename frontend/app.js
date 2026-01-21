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

function badgeClass(status) {
  return status === "approved" ? "approved" : status === "rejected" ? "rejected" : "pending";
}

function statusText(status) {
  return status === "approved" ? "已通过" : status === "rejected" ? "已驳回" : "待处理";
}

function typeText(t) {
  return t === "leave" ? "请假" : t === "expense" ? "报销" : "通用";
}

function stepText(step) {
  return step === "manager" ? "直属领导审批" : step === "finance" ? "财务审批" : "管理员审批";
}

let currentMe = null;
let currentTab = "create";

function setTab(tab) {
  currentTab = tab;
  for (const t of ["create", "requests", "inbox", "users"]) {
    const el = $(`#tab-${t}`);
    if (el) el.hidden = t !== tab;
  }
  document.querySelectorAll(".tabbtn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  if (tab === "requests") refreshRequests();
  if (tab === "inbox") refreshInbox();
  if (tab === "users") refreshUsers();
}

async function refreshMe() {
  try {
    return await api("/api/me");
  } catch {
    return null;
  }
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

  $("#usersTabBtn").hidden = currentMe.role !== "admin";
  $("#scopeWrap").hidden = currentMe.role !== "admin";

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
$("#refreshUsersBtn").onclick = refreshUsers;
$("#scopeAll").onchange = refreshRequests;

$("#createBtn").onclick = async () => {
  setError($("#createError"), "");
  const type = $("#reqType").value;
  const title = $("#reqTitle").value.trim();
  const body = $("#reqBody").value.trim();
  if (!title || !body) {
    setError($("#createError"), "标题和内容不能为空");
    return;
  }
  try {
    await api("/api/requests", { method: "POST", body: { type, title, body } });
    $("#reqTitle").value = "";
    $("#reqBody").value = "";
    currentTab = "requests";
    setTab("requests");
  } catch (e) {
    setError($("#createError"), e.code || "提交失败");
  }
};

refreshAll();
