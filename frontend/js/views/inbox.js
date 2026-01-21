async function refreshInbox() {
  const list = $("#inboxList");
  if (!currentMe) return;
  const data = await api("/api/inbox");
  renderInbox(list, data.items || []);
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

