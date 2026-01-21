# OA Backlog (TODO)

## Current (implemented)

- [x] Leave (`leave`)
- [x] Expense (`expense`) with amount threshold step (`min_amount`)
- [x] Purchase (`purchase`) with amount threshold step (`min_amount`)
- [x] Generic (`generic`)

## Next (platform capabilities)

- [ ] Workflow editor API (CRUD `workflow_definitions` / `workflow_steps`)
- [ ] Workflow editor UI (admin)
- [ ] More step conditions (e.g. `max_amount`, `dept_in`, `category_in`, `days>=N`)
- [ ] Parallel approvals / countersign (ALL / ANY)
- [ ] Return for changes / resubmit
- [ ] Withdraw / cancel request
- [ ] Delegate / proxy approvals
- [ ] CC / watchers + in-app notifications
- [ ] Attachments upload/download (local first)
- [ ] RBAC: permissions + role management + menu gating
- [ ] Org model: departments, positions, org chart, manager chain
- [ ] Search + filters + exports (CSV)

## Business flows (common OA request types)

### HR / Admin
- [ ] Overtime request (加班)
- [ ] Time correction /补卡
- [ ] Business trip request (出差)
- [ ] Outing request (外出)
- [ ] Travel reimbursement (差旅报销，细化到交通/住宿/补贴)
- [ ] Onboarding (入职)
- [ ] Probation -> regular (转正)
- [ ] Resignation (离职)
- [ ] Transfer / job change (调岗)
- [ ] Salary adjustment (调薪)

### Finance
- [ ] Borrow / loan request (借款)
- [ ] Payment request (付款申请: vendor/bank account)
- [ ] Budget pre-occupy (预算占用/预支)
- [ ] Invoice request (发票/开票)
- [ ] Asset capitalization approval (固定资产入账)

### Procurement / Assets
- [ ] Purchase (enhanced): multi-items + vendor + quotes + delivery date
- [ ] Compare quotes / bidding record (比价/询价)
- [ ] Goods receipt / acceptance (验收)
- [ ] Warehouse inbound/outbound (入库/出库)
- [ ] Asset request (设备申领)
- [ ] Asset transfer (资产调拨)
- [ ] Asset repair (维修)
- [ ] Asset scrap (报废)

### Contract / Seal / Legal
- [ ] Contract approval (合同审批)
- [ ] Legal review step (法务审查)
- [ ] Seal request (用章)
- [ ] Archiving (归档)

### IT / Access
- [ ] Account opening (账号开通)
- [ ] Permission access request (系统权限)
- [ ] VPN / email enabling (VPN/邮箱)
- [ ] Device request (设备申请)

### Facilities / Resources
- [ ] Meeting room booking (会议室)
- [ ] Vehicle request (用车)
- [ ] Supplies request (物品领用)

### Document / Compliance
- [ ] Document publishing (制度/公告发布)
- [ ] Read & acknowledge (阅读确认)

