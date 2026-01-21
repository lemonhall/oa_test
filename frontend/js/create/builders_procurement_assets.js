registerCreateBuilder("purchase", () => {
  const name = $("#purchaseItemName").value.trim();
  const qty = Number($("#purchaseQty").value || 0);
  const unit_price = Number($("#purchaseUnitPrice").value || 0);
  const reason = $("#purchaseReason").value.trim();
  if (!name || !qty || qty <= 0 || !unit_price || unit_price <= 0 || !reason) {
    return { error: "采购需要填写物品名称/数量/单价/原因" };
  }
  const amount = qty * unit_price;
  return { payload: { items: [{ name, qty, unit_price }], reason, amount } };
});

registerCreateBuilder("fixed_asset_accounting", () => {
  const asset_name = $("#faName").value.trim();
  const amount = Number($("#faAmount").value || 0);
  const acquired_date = $("#faDate").value;
  if (!asset_name || !amount || amount <= 0 || !acquired_date) {
    return { error: "固定资产入账需要填写资产名称/金额/购置日期" };
  }
  return { payload: { asset_name, amount, acquired_date } };
});

registerCreateBuilder("purchase_plus", () => {
  const name = $("#ppItemName").value.trim();
  const qty = Number($("#ppQty").value || 0);
  const unit_price = Number($("#ppUnitPrice").value || 0);
  const vendor = $("#ppVendor").value.trim();
  const delivery_date = $("#ppDeliveryDate").value;
  const reason = $("#ppReason").value.trim();
  if (!name || !qty || qty <= 0 || !unit_price || unit_price <= 0 || !vendor || !delivery_date || !reason) {
    return { error: "采购（增强）需要填写物品/数量/单价/供应商/交付日期/原因" };
  }
  return { payload: { items: [{ name, qty, unit_price }], vendor, delivery_date, reason } };
});

registerCreateBuilder("quote_compare", () => {
  const subject = $("#qcSubject").value.trim();
  const vendors = $("#qcVendors")
    .value.split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  const recommendation = $("#qcRecommendation").value.trim();
  if (!subject || vendors.length < 2 || !recommendation) return { error: "比价需要填写主题/至少2个供应商/推荐结论" };
  return { payload: { subject, vendors, recommendation } };
});

registerCreateBuilder("acceptance", () => {
  const purchase_ref = $("#accPurchaseRef").value.trim();
  const acceptance_date = $("#accDate").value;
  const summary = $("#accSummary").value.trim();
  if (!purchase_ref || !acceptance_date || !summary) return { error: "验收需要填写采购单号/验收日期/验收说明" };
  return { payload: { purchase_ref, acceptance_date, summary } };
});

registerCreateBuilder("inventory_in", () => {
  const warehouse = $("#invInWarehouse").value.trim();
  const date = $("#invInDate").value;
  const name = $("#invInItem").value.trim();
  const qty = Number($("#invInQty").value || 0);
  if (!warehouse || !date || !name || !qty || qty <= 0) return { error: "入库需要填写仓库/日期/物品/数量" };
  return { payload: { warehouse, date, items: [{ name, qty }] } };
});

registerCreateBuilder("inventory_out", () => {
  const warehouse = $("#invOutWarehouse").value.trim();
  const date = $("#invOutDate").value;
  const name = $("#invOutItem").value.trim();
  const qty = Number($("#invOutQty").value || 0);
  const reason = $("#invOutReason").value.trim();
  if (!warehouse || !date || !name || !qty || qty <= 0 || !reason) return { error: "出库需要填写仓库/日期/物品/数量/原因" };
  return { payload: { warehouse, date, items: [{ name, qty }], reason } };
});

registerCreateBuilder("device_claim", () => {
  const item = $("#dcItem").value.trim();
  const qty = Number($("#dcQty").value || 0);
  const reason = $("#dcReason").value.trim();
  if (!item || !qty || qty <= 0 || !reason) return { error: "设备申领需要填写物品/数量/原因" };
  return { payload: { item, qty, reason } };
});

registerCreateBuilder("asset_transfer", () => {
  const asset = $("#atAsset").value.trim();
  const from_user = $("#atFromUser").value.trim();
  const to_user = $("#atToUser").value.trim();
  const date = $("#atDate").value;
  if (!asset || !from_user || !to_user || !date) return { error: "资产调拨需要填写资产标识/原使用人/新使用人/日期" };
  return { payload: { asset, from_user, to_user, date } };
});

registerCreateBuilder("asset_maintenance", () => {
  const asset = $("#amAsset").value.trim();
  const issue = $("#amIssue").value.trim();
  const amount = Number($("#amAmount").value || 0);
  if (!asset || !issue || amount < 0) return { error: "资产维修需要填写资产标识/问题描述（费用可选）" };
  return { payload: { asset, issue, amount } };
});

registerCreateBuilder("asset_scrap", () => {
  const asset = $("#asAsset").value.trim();
  const scrap_date = $("#asDate").value;
  const reason = $("#asReason").value.trim();
  const amount = Number($("#asAmount").value || 0);
  if (!asset || !scrap_date || !reason || amount < 0) return { error: "资产报废需要填写资产标识/报废日期/原因（残值可选）" };
  return { payload: { asset, scrap_date, reason, amount } };
});

