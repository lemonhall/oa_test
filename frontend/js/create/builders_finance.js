registerCreateBuilder("expense", () => {
  const category = $("#expenseCategory").value.trim();
  const amount = Number($("#expenseAmount").value || 0);
  const reason = $("#expenseReason").value.trim();
  if (!amount || amount <= 0) return { error: "报销金额必须大于 0" };
  return { payload: { category, amount, reason } };
});

registerCreateBuilder("loan", () => {
  const amount = Number($("#loanAmount").value || 0);
  const reason = $("#loanReason").value.trim();
  if (!amount || amount <= 0 || !reason) return { error: "借款需要填写金额/用途" };
  return { payload: { amount, reason } };
});

registerCreateBuilder("payment", () => {
  const payee = $("#paymentPayee").value.trim();
  const amount = Number($("#paymentAmount").value || 0);
  const purpose = $("#paymentPurpose").value.trim();
  if (!payee || !amount || amount <= 0 || !purpose) return { error: "付款需要填写收款方/金额/用途" };
  return { payload: { payee, amount, purpose } };
});

registerCreateBuilder("budget", () => {
  const dept = $("#budgetDept").value.trim();
  const period = $("#budgetPeriod").value.trim();
  const amount = Number($("#budgetAmount").value || 0);
  const purpose = $("#budgetPurpose").value.trim();
  if (!dept || !period || !amount || amount <= 0 || !purpose) return { error: "预算需要填写部门/期间/金额/用途" };
  return { payload: { dept, period, amount, purpose } };
});

registerCreateBuilder("invoice", () => {
  const title = $("#invoiceTitle").value.trim();
  const amount = Number($("#invoiceAmount").value || 0);
  const purpose = $("#invoicePurpose").value.trim();
  if (!title || !amount || amount <= 0 || !purpose) return { error: "开票需要填写抬头/金额/用途" };
  return { payload: { title, amount, purpose } };
});

