async function refreshMe() {
  try {
    return await api("/api/me");
  } catch {
    return null;
  }
}

function hasPerm(key) {
  if (!currentMe) return false;
  const perms = currentMe.permissions || [];
  return perms.includes("*") || perms.includes(key);
}

