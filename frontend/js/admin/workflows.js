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
  renderWfStepsEditor([{ step_order: 1, step_key: "admin", assignee_kind: "role", assignee_value: "admin" }]);
  const det = $("#wfStepsJsonDetails");
  if (det) det.hidden = true;
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
  renderWfStepsEditor(data.steps || []);
  const det = $("#wfStepsJsonDetails");
  if (det) det.hidden = true;
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
  const steps = readWfStepsEditor();
  if (!steps.length) {
    $("#wfMsg").textContent = "至少需要 1 个步骤";
    return;
  }
  for (const s of steps) {
    if (!s.step_key) {
      $("#wfMsg").textContent = "step_key 不能为空";
      return;
    }
    if (!s.assignee_kind) {
      $("#wfMsg").textContent = "assignee_kind 不能为空";
      return;
    }
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

