function fmtTime(ts) {
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

function badgeClass(status) {
  if (status === "approved") return "approved";
  if (["rejected", "canceled", "withdrawn", "voided"].includes(status)) return "rejected";
  return "pending";
}

function statusText(status) {
  if (status === "approved") return "已通过";
  if (status === "rejected") return "已驳回";
  if (status === "pending") return "待处理";
  if (status === "canceled") return "已取消";
  if (status === "returned") return "已退回";
  if (status === "changes_requested") return "需修改";
  if (status === "resubmitted") return "已重提";
  if (status === "withdrawn") return "已撤回";
  if (status === "voided") return "已作废";
  return String(status || "");
}
