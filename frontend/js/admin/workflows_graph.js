let wfStepsEditorViewMode = "table";
let wfGraphSelectedIdx = 0;

function _wfEllipsize(s, maxLen) {
  const t = String(s || "");
  return t.length > maxLen ? `${t.slice(0, Math.max(0, maxLen - 1))}…` : t;
}

function _wfAssigneeSummary(step) {
  const kind = String(step?.assignee_kind || "");
  const v = step?.assignee_value == null ? "" : String(step.assignee_value);
  if (kind === "manager") return "直属领导";
  if (kind === "role") return `角色：${v || "（未填）"}`;
  if (kind === "user") return `用户：${v || "（未填）"}`;
  if (kind === "users_any") return `会签（任一）：${v === "all" ? "全员" : v || "（未填）"}`;
  if (kind === "users_all") return `会签（全部）：${v === "all" ? "全员" : v || "（未填）"}`;
  return kind || "（未知）";
}

function _wfConditionSummary(step) {
  const kind = step?.condition_kind == null ? "" : String(step.condition_kind);
  const v = step?.condition_value == null ? "" : String(step.condition_value);
  if (!kind) return "无";
  const map = {
    min_amount: "最低金额",
    max_amount: "最高金额",
    min_days: "最少天数",
    dept_in: "部门包含",
    category_in: "类别包含",
  };
  const label = map[kind] || kind;
  return v ? `${label}：${v}` : label;
}

function _wfScrollToStepRow(idx) {
  const row = document.querySelector(`[data-wf-step-idx="${idx}"]`);
  if (!row) return;
  row.scrollIntoView({ block: "nearest" });
  row.classList.add("flash");
  setTimeout(() => row.classList.remove("flash"), 800);
}

function setWfStepsEditorViewMode(mode) {
  wfStepsEditorViewMode = mode === "graph" ? "graph" : "table";
  const list = $("#wfStepsList");
  const panel = $("#wfStepsGraphPanel");
  if (list) list.hidden = wfStepsEditorViewMode === "graph";
  if (panel) panel.hidden = wfStepsEditorViewMode !== "graph";
  const tableBtn = $("#wfViewTableBtn");
  const graphBtn = $("#wfViewGraphBtn");
  if (tableBtn) tableBtn.classList.toggle("active", wfStepsEditorViewMode === "table");
  if (graphBtn) graphBtn.classList.toggle("active", wfStepsEditorViewMode === "graph");
  renderWfStepsGraph(wfStepsDraft || []);
}

function _wfUpdateGraphOps(steps) {
  const n = Array.isArray(steps) ? steps.length : 0;
  wfGraphSelectedIdx = Math.min(Math.max(0, wfGraphSelectedIdx), Math.max(0, n - 1));
  const selected = $("#wfGraphSelected");
  if (selected) selected.textContent = n ? `当前：第 ${wfGraphSelectedIdx + 1} 步` : "暂无步骤";

  const upBtn = $("#wfGraphMoveUpBtn");
  const downBtn = $("#wfGraphMoveDownBtn");
  const delBtn = $("#wfGraphDeleteBtn");
  if (upBtn) upBtn.disabled = !n || wfGraphSelectedIdx <= 0;
  if (downBtn) downBtn.disabled = !n || wfGraphSelectedIdx >= n - 1;
  if (delBtn) delBtn.disabled = !n;
}

function renderWfStepsGraph(steps) {
  const canvas = $("#wfStepsGraphCanvas");
  if (!canvas) return;
  const arr = Array.isArray(steps) ? steps : [];
  canvas.innerHTML = "";
  _wfUpdateGraphOps(arr);
  if (!arr.length) {
    canvas.innerHTML = '<div class="muted" style="padding:10px">暂无步骤</div>';
    return;
  }

  const svgNS = "http://www.w3.org/2000/svg";
  const svgW = 760;
  const nodeW = 620;
  const nodeH = 76;
  const pad = 18;
  const gap = 26;
  const svgH = pad * 2 + arr.length * nodeH + (arr.length - 1) * gap;
  const x = (svgW - nodeW) / 2;

  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${svgW} ${svgH}`);
  svg.style.width = "100%";
  svg.style.height = `${svgH}px`;

  const defs = document.createElementNS(svgNS, "defs");
  const marker = document.createElementNS(svgNS, "marker");
  marker.setAttribute("id", "wfArrow");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "10");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "7");
  marker.setAttribute("markerHeight", "7");
  marker.setAttribute("orient", "auto-start-reverse");
  const tip = document.createElementNS(svgNS, "path");
  tip.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  tip.setAttribute("fill", "rgba(255,255,255,0.55)");
  marker.appendChild(tip);
  defs.appendChild(marker);
  svg.appendChild(defs);

  for (let i = 0; i < arr.length; i++) {
    const y = pad + i * (nodeH + gap);
    const cx = x + nodeW / 2;
    if (i < arr.length - 1) {
      const line = document.createElementNS(svgNS, "path");
      line.setAttribute("d", `M ${cx} ${y + nodeH} L ${cx} ${y + nodeH + gap}`);
      line.setAttribute("stroke", "rgba(255,255,255,0.22)");
      line.setAttribute("stroke-width", "2");
      line.setAttribute("marker-end", "url(#wfArrow)");
      svg.appendChild(line);
    }

    const step = arr[i] || {};
    const g = document.createElementNS(svgNS, "g");
    g.setAttribute("data-idx", String(i));
    g.setAttribute("class", `wf-graph-node${i === wfGraphSelectedIdx ? " selected" : ""}`);

    const rect = document.createElementNS(svgNS, "rect");
    rect.setAttribute("x", String(x));
    rect.setAttribute("y", String(y));
    rect.setAttribute("width", String(nodeW));
    rect.setAttribute("height", String(nodeH));
    rect.setAttribute("rx", "14");
    g.appendChild(rect);

    const title = document.createElementNS(svgNS, "text");
    title.setAttribute("x", String(x + 16));
    title.setAttribute("y", String(y + 26));
    title.setAttribute("class", "wf-graph-title");
    const stepKey = String(step.step_key || "").trim();
    const titleText = `${i + 1}. ${
      typeof stepText === "function" ? stepText(stepKey) : "审批"
    }（${stepKey || "未命名"}）`;
    title.textContent = _wfEllipsize(titleText, 46);
    g.appendChild(title);

    const sub = document.createElementNS(svgNS, "text");
    sub.setAttribute("x", String(x + 16));
    sub.setAttribute("y", String(y + 48));
    sub.setAttribute("class", "wf-graph-sub");
    sub.textContent = _wfEllipsize(`指派：${_wfAssigneeSummary(step)}`, 66);
    g.appendChild(sub);

    const cond = document.createElementNS(svgNS, "text");
    cond.setAttribute("x", String(x + 16));
    cond.setAttribute("y", String(y + 68));
    cond.setAttribute("class", "wf-graph-sub");
    cond.textContent = _wfEllipsize(`条件：${_wfConditionSummary(step)}`, 66);
    g.appendChild(cond);

    svg.appendChild(g);
  }

  svg.addEventListener("click", (e) => {
    let el = e.target;
    while (el && el !== svg) {
      if (el.getAttribute && el.getAttribute("data-idx") != null) break;
      el = el.parentNode;
    }
    if (!el || el === svg) return;
    const idx = Number(el.getAttribute("data-idx"));
    if (!Number.isFinite(idx)) return;
    wfGraphSelectedIdx = Math.min(Math.max(0, idx), arr.length - 1);
    _wfUpdateGraphOps(arr);
    renderWfStepsGraph(arr);
  });

  canvas.appendChild(svg);
}

function bindWfStepsGraphEditorEvents() {
  const tableBtn = $("#wfViewTableBtn");
  const graphBtn = $("#wfViewGraphBtn");
  if (tableBtn) tableBtn.onclick = () => setWfStepsEditorViewMode("table");
  if (graphBtn) graphBtn.onclick = () => setWfStepsEditorViewMode("graph");

  const editBtn = $("#wfGraphEditBtn");
  if (editBtn)
    editBtn.onclick = () => {
      setWfStepsEditorViewMode("table");
      _wfScrollToStepRow(wfGraphSelectedIdx);
    };

  const upBtn = $("#wfGraphMoveUpBtn");
  if (upBtn)
    upBtn.onclick = () => {
      if (!Array.isArray(wfStepsDraft) || wfGraphSelectedIdx <= 0) return;
      [wfStepsDraft[wfGraphSelectedIdx - 1], wfStepsDraft[wfGraphSelectedIdx]] = [
        wfStepsDraft[wfGraphSelectedIdx],
        wfStepsDraft[wfGraphSelectedIdx - 1],
      ];
      wfGraphSelectedIdx -= 1;
      renderWfStepsEditor(wfStepsDraft);
    };

  const downBtn = $("#wfGraphMoveDownBtn");
  if (downBtn)
    downBtn.onclick = () => {
      if (!Array.isArray(wfStepsDraft) || wfGraphSelectedIdx >= wfStepsDraft.length - 1) return;
      [wfStepsDraft[wfGraphSelectedIdx + 1], wfStepsDraft[wfGraphSelectedIdx]] = [
        wfStepsDraft[wfGraphSelectedIdx],
        wfStepsDraft[wfGraphSelectedIdx + 1],
      ];
      wfGraphSelectedIdx += 1;
      renderWfStepsEditor(wfStepsDraft);
    };

  const delBtn = $("#wfGraphDeleteBtn");
  if (delBtn)
    delBtn.onclick = () => {
      if (!Array.isArray(wfStepsDraft) || !wfStepsDraft.length) return;
      wfStepsDraft.splice(wfGraphSelectedIdx, 1);
      wfGraphSelectedIdx = Math.min(wfGraphSelectedIdx, Math.max(0, wfStepsDraft.length - 1));
      renderWfStepsEditor(wfStepsDraft);
    };

  setWfStepsEditorViewMode(wfStepsEditorViewMode);
}
