registerCreateBuilder("contract", () => {
  const name = $("#contractName").value.trim();
  const party = $("#contractParty").value.trim();
  const amount = Number($("#contractAmount").value || 0);
  const start_date = $("#contractStart").value;
  const end_date = $("#contractEnd").value;
  const summary = $("#contractSummary").value.trim();
  if (!name || !party || !amount || amount <= 0 || !start_date || !end_date) {
    return { error: "合同审批需要填写合同名称/对方/金额/开始/结束" };
  }
  return { payload: { name, party, amount, start_date, end_date, summary } };
});

registerCreateBuilder("legal_review", () => {
  const subject = $("#legalSubject").value.trim();
  const risk_level = $("#legalRisk").value;
  const notes = $("#legalNotes").value.trim();
  if (!subject || !risk_level) return { error: "法务审查需要填写主题/风险等级" };
  return { payload: { subject, risk_level, notes } };
});

registerCreateBuilder("seal", () => {
  const document = $("#sealDocument").value.trim();
  const seal_type = $("#sealType").value;
  const purpose = $("#sealPurpose").value.trim();
  const needed_date = $("#sealNeeded").value;
  if (!document || !seal_type || !purpose || !needed_date) return { error: "用章需要填写文件/类型/用途/日期" };
  return { payload: { document, seal_type, purpose, needed_date } };
});

registerCreateBuilder("archive", () => {
  const document = $("#archiveDocument").value.trim();
  const archive_type = $("#archiveType").value.trim();
  const retention_years = Number($("#archiveYears").value || 0);
  if (!document || !archive_type || !retention_years || retention_years <= 0) return { error: "归档需要填写文件/类型/年限" };
  return { payload: { document, archive_type, retention_years } };
});

registerCreateBuilder("account_open", () => {
  const system = $("#aoSystem").value.trim();
  const account = $("#aoAccount").value.trim();
  const dept = $("#aoDept").value.trim();
  const reason = $("#aoReason").value.trim();
  if (!system || !account || !dept || !reason) return { error: "账号开通需要填写系统/账号/部门/原因" };
  return { payload: { system, account, dept, reason } };
});

registerCreateBuilder("permission", () => {
  const system = $("#permSystem").value.trim();
  const permission = $("#permValue").value.trim();
  const duration_days = Number($("#permDays").value || 0);
  const reason = $("#permReason").value.trim();
  if (!system || !permission || !duration_days || duration_days <= 0 || !reason) return { error: "权限申请需要填写系统/权限/期限/原因" };
  return { payload: { system, permission, duration_days, reason } };
});

registerCreateBuilder("vpn_email", () => {
  const kind = $("#veKind").value;
  const account = $("#veAccount").value.trim();
  const reason = $("#veReason").value.trim();
  if (!kind || !account || !reason) return { error: "VPN/邮箱开通需要填写类型/账号/原因" };
  return { payload: { kind, account, reason } };
});

registerCreateBuilder("it_device", () => {
  const item = $("#itDevItem").value.trim();
  const qty = Number($("#itDevQty").value || 0);
  const reason = $("#itDevReason").value.trim();
  if (!item || !qty || qty <= 0 || !reason) return { error: "设备申请需要填写设备/数量/原因" };
  return { payload: { item, qty, reason } };
});

registerCreateBuilder("meeting_room", () => {
  const room = $("#mrRoom").value.trim();
  const date = $("#mrDate").value;
  const start_time = $("#mrStart").value;
  const end_time = $("#mrEnd").value;
  const subject = $("#mrSubject").value.trim();
  if (!room || !date || !start_time || !end_time || !subject) return { error: "会议室预定需要填写会议室/日期/开始/结束/主题" };
  return { payload: { room, date, start_time, end_time, subject } };
});

registerCreateBuilder("car", () => {
  const date = $("#carDate").value;
  const start_time = $("#carStart").value;
  const end_time = $("#carEnd").value;
  const from = $("#carFrom").value.trim();
  const to = $("#carTo").value.trim();
  const reason = $("#carReason").value.trim();
  if (!date || !start_time || !end_time || !from || !to || !reason) return { error: "用车需要填写日期/开始/结束/出发地/目的地/原因" };
  return { payload: { date, start_time, end_time, from, to, reason } };
});

registerCreateBuilder("supplies", () => {
  const name = $("#supItem").value.trim();
  const qty = Number($("#supQty").value || 0);
  const reason = $("#supReason").value.trim();
  if (!name || !qty || qty <= 0 || !reason) return { error: "物品领用需要填写物品/数量/原因" };
  return { payload: { items: [{ name, qty }], reason } };
});

registerCreateBuilder("policy_announcement", () => {
  const subject = $("#paSubject").value.trim();
  const content = $("#paContent").value.trim();
  const effective_date = $("#paEffective").value;
  if (!subject || !content) return { error: "制度/公告需要填写主题/内容" };
  return { payload: { subject, content, effective_date } };
});

registerCreateBuilder("read_ack", () => {
  const subject = $("#raSubject").value.trim();
  const content = $("#raContent").value.trim();
  const due_date = $("#raDue").value;
  if (!subject || !content) return { error: "阅读确认需要填写主题/内容" };
  return { payload: { subject, content, due_date } };
});

