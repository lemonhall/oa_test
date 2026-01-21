function showCreateFields(type) {
  const map = {
    leave: "leaveFields",
    expense: "expenseFields",
    purchase: "purchaseFields",
    overtime: "overtimeFields",
    attendance_correction: "attendanceFields",
    business_trip: "businessTripFields",
    outing: "outingFields",
    travel_expense: "travelExpenseFields",
    onboarding: "onboardingFields",
    probation: "probationFields",
    resignation: "resignationFields",
    job_transfer: "jobTransferFields",
    salary_adjustment: "salaryAdjustFields",
    loan: "loanFields",
    payment: "paymentFields",
    budget: "budgetFields",
    invoice: "invoiceFields",
    fixed_asset_accounting: "fixedAssetFields",
    purchase_plus: "purchasePlusFields",
    quote_compare: "quoteCompareFields",
    acceptance: "acceptanceFields",
    inventory_in: "inventoryInFields",
    inventory_out: "inventoryOutFields",
    device_claim: "deviceClaimFields",
    asset_transfer: "assetTransferFields",
    asset_maintenance: "assetMaintenanceFields",
    asset_scrap: "assetScrapFields",
    contract: "contractFields",
    legal_review: "legalReviewFields",
    seal: "sealFields",
    archive: "archiveFields",
    account_open: "accountOpenFields",
    permission: "permissionFields",
    vpn_email: "vpnEmailFields",
    it_device: "itDeviceFields",
    meeting_room: "meetingRoomFields",
    car: "carFields",
    supplies: "suppliesFields",
    policy_announcement: "policyAnnouncementFields",
    read_ack: "readAckFields",
  };
  for (const id of Object.values(map)) {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
  }
  const target = map[type];
  if (target) {
    const el = document.getElementById(target);
    if (el) el.hidden = false;
  }
}

function groupWorkflows(items) {
  const groups = new Map();
  for (const w of items) {
    const cat = categoryText(w.category || "Other");
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(w);
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function optionLabel(w) {
  const scope = w.scope_kind === "dept" ? `部门：${w.scope_value}` : "公司通用";
  return `${workflowNameFromVariant(w)}（${scope}）`;
}

async function loadWorkflows() {
  const data = await api("/api/workflows");
  workflowItems = data.items || [];
  workflowsByKey = {};
  for (const w of workflowItems) workflowsByKey[w.key] = w;

  const sel = $("#workflowKey");
  sel.innerHTML = "";
  const groups = groupWorkflows(workflowItems);
  for (const [cat, items] of groups) {
    const og = document.createElement("optgroup");
    og.label = cat;
    for (const w of items) {
      const opt = document.createElement("option");
      opt.value = w.key;
      opt.textContent = optionLabel(w);
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }

  let defaultKey = workflowItems.find((w) => w.is_default)?.key || workflowItems[0]?.key;
  if (defaultKey) sel.value = defaultKey;
  onWorkflowChanged();
}

function onWorkflowChanged() {
  const sel = $("#workflowKey");
  const wf = workflowsByKey[sel.value];
  if (!wf) return;
  const cat = categoryText(wf.category);
  const name = workflowNameFromVariant(wf);
  $("#workflowHint").textContent = `类别：${cat} · 流程：${name}`;
  showCreateFields(wf.request_type);
}
