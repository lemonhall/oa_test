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
  $("#whoami").textContent = `当前：${currentMe.username}（${roleText(currentMe.role)}）`;

  $("#usersTabBtn").hidden = !hasPerm("users:manage");
  $("#rolesTabBtn").hidden = !hasPerm("rbac:manage");
  $("#scopeWrap").hidden = !hasPerm("requests:read_all");
  $("#workflowsTabBtn").hidden = !hasPerm("workflows:manage");

  if (!workflowItems.length) {
    await loadWorkflows().catch(() => {});
  }
  setTab(currentTab);
}
