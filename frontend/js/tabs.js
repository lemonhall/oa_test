function setTab(tab) {
  currentTab = tab;
  for (const t of ["create", "requests", "inbox", "notifications", "roles", "users", "workflows"]) {
    const el = $(`#tab-${t}`);
    if (el) el.hidden = t !== tab;
  }
  document.querySelectorAll(".tabbtn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  if (tab === "requests") refreshRequests();
  if (tab === "inbox") refreshInbox();
  if (tab === "notifications") refreshNotifications();
  if (tab === "roles") refreshRoles();
  if (tab === "users") refreshUsers();
  if (tab === "workflows") refreshAdminWorkflows();
}

