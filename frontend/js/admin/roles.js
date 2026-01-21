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

