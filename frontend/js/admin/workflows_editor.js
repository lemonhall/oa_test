function _clone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function _normalizeSteps(steps) {
  const out = Array.isArray(steps) ? steps : [];
  return out
    .filter((s) => s && typeof s === "object")
    .map((s, i) => ({
      step_order: i + 1,
      step_key: String(s.step_key || "").trim(),
      assignee_kind: String(s.assignee_kind || "role"),
      assignee_value: s.assignee_value == null ? null : String(s.assignee_value),
      condition_kind: s.condition_kind == null ? null : String(s.condition_kind),
      condition_value: s.condition_value == null ? null : String(s.condition_value),
    }));
}

function renderWfStepsEditor(steps) {
  wfStepsDraft = _normalizeSteps(_clone(steps || []));
  const list = $("#wfStepsList");
  if (!list) return;
  list.innerHTML = "";

  const header = document.createElement("div");
  header.className = "row muted";
  header.style.gap = "10px";
  header.style.fontSize = "13px";
  header.style.marginBottom = "8px";
  header.innerHTML =
    '<div style="width:80px">顺序</div><div style="width:160px">step_key</div><div style="width:170px">assignee_kind</div><div style="flex:1">assignee_value</div><div style="width:160px">condition_kind</div><div style="flex:1">condition_value</div><div style="width:90px">操作</div>';
  list.appendChild(header);

  const conditionOptions = [
    ["", "无"],
    ["min_amount", "min_amount"],
    ["max_amount", "max_amount"],
    ["min_days", "min_days"],
    ["dept_in", "dept_in"],
    ["category_in", "category_in"],
  ];

  wfStepsDraft.forEach((s, idx) => {
    const row = document.createElement("div");
    row.className = "row";
    row.style.gap = "10px";
    row.style.alignItems = "flex-end";

    const orderWrap = document.createElement("div");
    orderWrap.style.width = "80px";
    orderWrap.className = "row";
    orderWrap.style.gap = "6px";
    orderWrap.style.alignItems = "center";
    const orderText = document.createElement("div");
    orderText.className = "muted";
    orderText.style.width = "24px";
    orderText.style.textAlign = "right";
    orderText.textContent = String(idx + 1);
    const upBtn = document.createElement("button");
    upBtn.className = "btn btn-secondary";
    upBtn.type = "button";
    upBtn.textContent = "↑";
    upBtn.disabled = idx === 0;
    upBtn.onclick = () => {
      const arr = wfStepsDraft;
      [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]];
      renderWfStepsEditor(arr);
    };
    const downBtn = document.createElement("button");
    downBtn.className = "btn btn-secondary";
    downBtn.type = "button";
    downBtn.textContent = "↓";
    downBtn.disabled = idx === wfStepsDraft.length - 1;
    downBtn.onclick = () => {
      const arr = wfStepsDraft;
      [arr[idx + 1], arr[idx]] = [arr[idx], arr[idx + 1]];
      renderWfStepsEditor(arr);
    };
    orderWrap.appendChild(orderText);
    orderWrap.appendChild(upBtn);
    orderWrap.appendChild(downBtn);

    const stepKey = document.createElement("input");
    stepKey.style.width = "160px";
    stepKey.placeholder = "例如：admin/manager";
    stepKey.setAttribute("list", "wfStepKeyList");
    stepKey.value = s.step_key || "";
    stepKey.oninput = () => (wfStepsDraft[idx].step_key = stepKey.value.trim());

    const assigneeKind = document.createElement("select");
    assigneeKind.style.width = "170px";
    for (const k of ["manager", "role", "user", "users_any", "users_all"]) {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = k;
      assigneeKind.appendChild(opt);
    }
    assigneeKind.value = s.assignee_kind || "role";
    assigneeKind.onchange = () => {
      wfStepsDraft[idx].assignee_kind = assigneeKind.value;
      if (assigneeKind.value === "manager") wfStepsDraft[idx].assignee_value = null;
      renderWfStepsEditor(wfStepsDraft);
    };

    const assigneeValueWrap = document.createElement("div");
    assigneeValueWrap.style.flex = "1";
    const assigneeValue = document.createElement("input");
    assigneeValue.placeholder = assigneeKind.value === "role" ? "role 名称，例如：admin" : "user_id 或 all 或 1,2,3";
    assigneeValue.value = s.assignee_value == null ? "" : String(s.assignee_value);
    assigneeValue.oninput = () => (wfStepsDraft[idx].assignee_value = assigneeValue.value.trim() || null);
    if (assigneeKind.value === "manager") {
      assigneeValue.disabled = true;
      assigneeValue.placeholder = "（manager 不需要值）";
    }
    const allBtn = document.createElement("button");
    allBtn.className = "btn btn-secondary";
    allBtn.type = "button";
    allBtn.textContent = "全员";
    allBtn.hidden = !["users_all", "users_any"].includes(assigneeKind.value);
    allBtn.onclick = () => {
      wfStepsDraft[idx].assignee_value = "all";
      renderWfStepsEditor(wfStepsDraft);
    };
    const avRow = document.createElement("div");
    avRow.className = "row";
    avRow.style.gap = "6px";
    avRow.appendChild(assigneeValue);
    avRow.appendChild(allBtn);
    assigneeValueWrap.appendChild(avRow);

    const conditionKind = document.createElement("select");
    conditionKind.style.width = "160px";
    for (const [v, label] of conditionOptions) {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = label;
      conditionKind.appendChild(opt);
    }
    conditionKind.value = s.condition_kind || "";
    conditionKind.onchange = () => {
      wfStepsDraft[idx].condition_kind = conditionKind.value || null;
      if (!conditionKind.value) wfStepsDraft[idx].condition_value = null;
      renderWfStepsEditor(wfStepsDraft);
    };

    const conditionValue = document.createElement("input");
    conditionValue.style.flex = "1";
    conditionValue.placeholder = conditionKind.value ? "例如：5000 / IT,HR" : "（无）";
    conditionValue.value = s.condition_value == null ? "" : String(s.condition_value);
    conditionValue.oninput = () => (wfStepsDraft[idx].condition_value = conditionValue.value.trim() || null);
    conditionValue.disabled = !conditionKind.value;

    const ops = document.createElement("div");
    ops.style.width = "90px";
    ops.className = "row";
    ops.style.gap = "6px";
    const delBtn = document.createElement("button");
    delBtn.className = "btn btn-secondary";
    delBtn.type = "button";
    delBtn.textContent = "删除";
    delBtn.onclick = () => {
      wfStepsDraft.splice(idx, 1);
      renderWfStepsEditor(wfStepsDraft);
    };
    ops.appendChild(delBtn);

    row.appendChild(orderWrap);
    row.appendChild(stepKey);
    row.appendChild(assigneeKind);
    row.appendChild(assigneeValueWrap);
    row.appendChild(conditionKind);
    row.appendChild(conditionValue);
    row.appendChild(ops);
    list.appendChild(row);
  });
}

function readWfStepsEditor() {
  const steps = _normalizeSteps(_clone(wfStepsDraft || []));
  return steps.map((s, i) => ({
    step_order: i + 1,
    step_key: String(s.step_key || "").trim(),
    assignee_kind: String(s.assignee_kind || "role"),
    assignee_value:
      s.assignee_value == null || String(s.assignee_value).trim() === "" ? null : String(s.assignee_value).trim(),
    condition_kind:
      s.condition_kind == null || String(s.condition_kind).trim() === "" ? null : String(s.condition_kind).trim(),
    condition_value:
      s.condition_value == null || String(s.condition_value).trim() === "" ? null : String(s.condition_value).trim(),
  }));
}

