function fmtTime(ts) {
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

function badgeClass(status) {
  return status === "approved" ? "approved" : status === "rejected" ? "rejected" : "pending";
}

function statusText(status) {
  return status === "approved" ? "已通过" : status === "rejected" ? "已驳回" : "待处理";
}

