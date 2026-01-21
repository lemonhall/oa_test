function typeText(t) {
  const map = {
    leave: "请假",
    expense: "报销",
    purchase: "采购",
    overtime: "加班",
    attendance_correction: "补卡/改卡",
    business_trip: "出差",
    outing: "外出",
    travel_expense: "差旅报销",
    onboarding: "入职",
    probation: "转正",
    resignation: "离职",
    job_transfer: "调岗",
    salary_adjustment: "调薪",
    loan: "借款",
    payment: "付款",
    budget: "预算",
    invoice: "开票",
    fixed_asset_accounting: "固定资产入账",
    purchase_plus: "采购（增强）",
    quote_compare: "比价/询价",
    acceptance: "验收",
    inventory_in: "入库",
    inventory_out: "出库",
    device_claim: "设备申领",
    asset_transfer: "资产调拨",
    asset_maintenance: "资产维修",
    asset_scrap: "资产报废",
    contract: "合同审批",
    legal_review: "法务审查",
    seal: "用章申请",
    archive: "归档",
    account_open: "账号开通",
    permission: "系统权限申请",
    vpn_email: "VPN/邮箱开通",
    it_device: "设备申请",
    meeting_room: "会议室预定",
    car: "用车申请",
    supplies: "物品领用",
    policy_announcement: "制度/公告发布",
    read_ack: "阅读确认",
  };
  return map[t] || "通用";
}

function stepText(step) {
  return step === "manager"
    ? "直属领导审批"
    : step === "gm"
    ? "总经理审批"
    : step === "hr"
    ? "人事审批"
    : step === "legal"
    ? "法务审批"
    : step === "finance"
    ? "财务审批"
    : step === "procurement"
    ? "采购审批"
    : step === "it"
    ? "IT审批"
    : step === "admin"
    ? "行政/管理员审批"
    : step === "ack"
    ? "阅读确认"
    : "审批";
}

