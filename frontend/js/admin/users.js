async function refreshUsers() {
  const list = $("#usersList");
  if (!currentMe || currentMe.role !== "admin") return;
  const data = await api("/api/users");
  renderUsers(list, data.items || []);
}

function renderUsers(list, items) {
  if (!items.length) return renderEmpty(list, "暂无用户");
  list.innerHTML = "";

  const options = [{ id: "", label: "（无）" }, ...items.map((u) => ({ id: String(u.id), label: `${u.username}（${u.role}）` }))];

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

