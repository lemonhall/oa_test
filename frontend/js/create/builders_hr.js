registerCreateBuilder("leave", () => {
  const start_date = $("#leaveStart").value;
  const end_date = $("#leaveEnd").value;
  const days = Number($("#leaveDays").value || 0);
  const reason = $("#leaveReason").value.trim();
  if (!start_date || !end_date || !days || !reason) return { error: "请假需要填写开始/结束/天数/原因" };
  return { payload: { start_date, end_date, days, reason } };
});

registerCreateBuilder("overtime", () => {
  const date = $("#overtimeDate").value;
  const hours = Number($("#overtimeHours").value || 0);
  const reason = $("#overtimeReason").value.trim();
  if (!date || !hours || hours <= 0 || !reason) return { error: "加班需要填写日期/时长/原因" };
  return { payload: { date, hours, reason } };
});

registerCreateBuilder("attendance_correction", () => {
  const date = $("#attDate").value;
  const kind = $("#attKind").value;
  const time = $("#attTime").value;
  const reason = $("#attReason").value.trim();
  if (!date || !kind || !time || !reason) return { error: "补卡需要填写日期/类型/时间/原因" };
  return { payload: { date, kind, time, reason } };
});

registerCreateBuilder("business_trip", () => {
  const start_date = $("#tripStart").value;
  const end_date = $("#tripEnd").value;
  const destination = $("#tripDestination").value.trim();
  const purpose = $("#tripPurpose").value.trim();
  if (!start_date || !end_date || !destination || !purpose) return { error: "出差需要填写开始/结束/目的地/事由" };
  return { payload: { start_date, end_date, destination, purpose } };
});

registerCreateBuilder("outing", () => {
  const date = $("#outingDate").value;
  const start_time = $("#outingStart").value;
  const end_time = $("#outingEnd").value;
  const destination = $("#outingDestination").value.trim();
  const reason = $("#outingReason").value.trim();
  if (!date || !start_time || !end_time || !destination || !reason) return { error: "外出需要填写日期/开始/结束/地点/原因" };
  return { payload: { date, start_time, end_time, destination, reason } };
});

registerCreateBuilder("travel_expense", () => {
  const start_date = $("#travelStart").value;
  const end_date = $("#travelEnd").value;
  const amount = Number($("#travelAmount").value || 0);
  const reason = $("#travelReason").value.trim();
  if (!start_date || !end_date || !amount || amount <= 0) return { error: "差旅报销需要填写开始/结束/金额" };
  return { payload: { start_date, end_date, amount, reason } };
});

registerCreateBuilder("onboarding", () => {
  const name = $("#onboardName").value.trim();
  const start_date = $("#onboardDate").value;
  const dept = $("#onboardDept").value.trim();
  const position = $("#onboardPosition").value.trim();
  if (!name || !start_date || !dept || !position) return { error: "入职需要填写姓名/日期/部门/岗位" };
  return { payload: { name, start_date, dept, position } };
});

registerCreateBuilder("probation", () => {
  const name = $("#probName").value.trim();
  const start_date = $("#probStart").value;
  const end_date = $("#probEnd").value;
  const result = $("#probResult").value;
  const comment = $("#probComment").value.trim();
  if (!name || !start_date || !end_date || !result) return { error: "转正需要填写姓名/开始/结束/结果" };
  return { payload: { name, start_date, end_date, result, comment } };
});

registerCreateBuilder("resignation", () => {
  const name = $("#resignName").value.trim();
  const last_day = $("#resignLastDay").value;
  const reason = $("#resignReason").value.trim();
  const handover = $("#resignHandover").value.trim();
  if (!name || !last_day || !reason) return { error: "离职需要填写姓名/最后工作日/离职原因" };
  return { payload: { name, last_day, reason, handover } };
});

registerCreateBuilder("job_transfer", () => {
  const name = $("#transferName").value.trim();
  const from_dept = $("#transferFrom").value.trim();
  const to_dept = $("#transferTo").value.trim();
  const effective_date = $("#transferDate").value;
  const reason = $("#transferReason").value.trim();
  if (!name || !from_dept || !to_dept || !effective_date) return { error: "调岗需要填写姓名/原部门/新部门/生效日期" };
  return { payload: { name, from_dept, to_dept, effective_date, reason } };
});

registerCreateBuilder("salary_adjustment", () => {
  const name = $("#salaryName").value.trim();
  const effective_date = $("#salaryDate").value;
  const from_salary = Number($("#salaryFrom").value || 0);
  const to_salary = Number($("#salaryTo").value || 0);
  const reason = $("#salaryReason").value.trim();
  if (!name || !effective_date || !from_salary || !to_salary) return { error: "调薪需要填写姓名/生效日期/原薪资/新薪资" };
  return { payload: { name, effective_date, from_salary, to_salary, reason } };
});

