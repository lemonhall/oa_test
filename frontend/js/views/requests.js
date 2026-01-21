async function refreshRequests() {
  const list = $("#requestsList");
  if (!currentMe) return;
  const scope = currentMe.role === "admin" && $("#scopeAll").checked ? "all" : "mine";
  const data = await api(`/api/requests?scope=${encodeURIComponent(scope)}`);
  renderRequests(list, data.items || []);
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
    wfBadge.textContent = item.workflow ? workflowNameFromRequestWorkflow(item.workflow) : "";

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
        (item.pending_task.assignee_role ? `角色：${roleText(item.pending_task.assignee_role)}` : "-");
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
            `- ${stepText(t.step_key)}：${statusText(t.status)}${
              t.decided_at ? `（${fmtTime(t.decided_at)} ${t.decided_by_username || ""}）` : ""
            }${t.comment ? ` · ${t.comment}` : ""}`
          );
        }
        if (events.length) {
          lines.push("");
          lines.push("事件：");
          for (const e of events) {
            const who = e.actor_username || "系统";
            const msg = cleanMessage(e.message);
            lines.push(`- ${fmtTime(e.created_at)} ${who} ${eventTypeText(e.event_type)}${msg ? ` · ${msg}` : ""}`);
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
