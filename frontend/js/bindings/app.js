function bindAppEvents() {
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
  $("#refreshNotificationsBtn").onclick = refreshNotifications;
  $("#refreshRolesBtn").onclick = refreshRoles;
  $("#refreshUsersBtn").onclick = refreshUsers;
  $("#refreshWorkflowsBtn").onclick = refreshAdminWorkflows;
  $("#scopeAll").onchange = refreshRequests;

  $("#workflowKey").onchange = onWorkflowChanged;

  $("#roleSelect").onchange = () => loadRole($("#roleSelect").value);
  $("#newRoleBtn").onclick = newRole;
  $("#saveRoleBtn").onclick = saveRole;
}

