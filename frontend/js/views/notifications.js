async function refreshNotifications() {
  const list = $("#notificationsList");
  if (!currentMe) return;
  const data = await api("/api/notifications");
  renderNotifications(list, data.items || []);
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
    title.textContent = `${eventTypeText(n.event_type)}${who} ${rid}`.trim();

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
    body.textContent = cleanMessage(n.message) || "";
    el.appendChild(body);

    const meta = document.createElement("div");
    meta.className = "item-meta";
    meta.textContent = `时间：${fmtTime(n.created_at)}`;
    el.appendChild(meta);

    list.appendChild(el);
  }
}
