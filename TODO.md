# OA 待办清单（Backlog / TODO）

## 已实现（当前）

- [x] 请假（`leave`）
- [x] 报销（`expense`，含金额阈值条件 `min_amount`）
- [x] 采购（`purchase`，含金额阈值条件 `min_amount`）
- [x] 采购（增强）（`purchase_plus`）
- [x] 通用（`generic`）

- [x] 加班申请（`overtime`）
- [x] 补卡/改卡申请（`attendance_correction`）
- [x] 出差申请（`business_trip`）
- [x] 外出申请（`outing`）
- [x] 差旅报销（`travel_expense`）
- [x] 入职流程（`onboarding`）
- [x] 转正流程（`probation`）
- [x] 离职流程（`resignation`）
- [x] 调岗流程（`job_transfer`）
- [x] 调薪流程（`salary_adjustment`）

- [x] 借款申请（`loan`）
- [x] 付款申请（`payment`）
- [x] 预算占用/预支（`budget`）
- [x] 发票/开票申请（`invoice`）
- [x] 固定资产入账审批（`fixed_asset_accounting`）

- [x] 比价/询价记录（`quote_compare`）
- [x] 验收流程（`acceptance`）
- [x] 入库（`inventory_in`）
- [x] 出库（`inventory_out`）
- [x] 设备申领（`device_claim`）
- [x] 资产调拨（`asset_transfer`）
- [x] 资产维修（`asset_maintenance`）
- [x] 资产报废（`asset_scrap`）

- [x] 合同审批（`contract`）
- [x] 法务审查（`legal_review`）
- [x] 用章申请（`seal`）
- [x] 合同/文件归档（`archive`）

- [x] 账号开通（`account_open`）
- [x] 系统权限申请（`permission`）
- [x] VPN/邮箱开通（`vpn_email`）
- [x] IT 设备申请（`it_device`）

- [x] 会议室预定（`meeting_room`）
- [x] 用车申请（`car`）
- [x] 物品领用（`supplies`）

- [x] 制度/公告发布（`policy_announcement`）
- [x] 阅读确认（`read_ack`）

## 平台能力（优先做）

- [x] 工作流管理 API（CRUD `workflow_variants` / `workflow_variant_steps`）
- [x] 工作流管理 UI（管理员）
- [x] 可视化流程编辑器（替代 JSON 文本）
- [x] 按部门的流程变体（scope：同一 `request_type` 不同部门不同审批链）
- [x] 更多步骤条件（例如：`max_amount`、`dept_in`、`category_in`、`days>=N`）
- [x] 并行会签 / 会审（基础：`users_all` / `users_any`）
- [x] 退回修改 / 重新提交
- [x] 撤回 / 作废
- [x] 转交（任务转交/重新指派）
- [x] 加签（插入额外审批人）
- [x] 代理审批（委托代办）
- [x] 抄送/关注人 + 站内通知
- [x] 附件上传/下载（先本地存储）
- [x] 权限体系（RBAC）：权限点 + 角色管理 + 菜单可见性
- [x] 组织架构：部门、岗位、组织树、上级链
- [x] 搜索 + 筛选 + 导出（CSV）

## 业务流程（常见 OA 申请类型）

### 人事 / 行政
- [x] 加班申请
- [x] 补卡/改卡申请
- [x] 出差申请
- [x] 外出申请
- [x] 差旅报销（细化到交通/住宿/补贴等）
- [x] 入职流程
- [x] 转正流程
- [x] 离职流程
- [x] 调岗流程
- [x] 调薪流程

### 财务
- [x] 借款申请
- [x] 付款申请（对公/对私，收款方信息）
- [x] 预算占用/预支
- [x] 发票/开票申请
- [x] 固定资产入账审批

### 采购 / 资产
- [x] 采购（增强版）：多物品 + 供应商 + 报价单 + 交付日期
- [x] 比价/询价记录
- [x] 验收流程
- [x] 入库/出库
- [x] 设备申领
- [x] 资产调拨
- [x] 资产维修
- [x] 资产报废

### 合同 / 用章 / 法务
- [x] 合同审批
- [x] 法务审查（会签）
- [x] 用章申请
- [x] 合同/文件归档

### IT / 权限
- [x] 账号开通
- [x] 系统权限申请
- [x] VPN/邮箱开通
- [x] 设备申请

### 资源 / 后勤
- [x] 会议室预定
- [x] 用车申请
- [x] 物品领用

### 公文 / 合规
- [x] 制度/公告发布
- [x] 阅读确认


## 下一阶段（建议）

### 代码健康（优先）

- [x] （无需拆分）`oa_server/auth.py` 已约 54 行
- [ ] 统一 `oa_server/` 与 `src/oa_server/` 的重复实现（只保留一套，避免双维护）
- [ ] 处理遗留 `oa_server/_db/db_monolith_legacy.py`（迁移完成后移除/归档）
- [ ] 拆分 `oa_server/_db/workflow_variants.py`（500+ 行，按 catalog/migrate/crud 拆）
- [ ] 拆分 `oa_server/_db/workflows_legacy.py`（350+ 行，按 seed/migrate 拆）
- [ ] 拆分 `frontend/index.html`（按 Tab/组件拆模板，减少单文件 1000+ 行）

### 表单/流程配置化（中优先）

- [ ] 表单定义 Schema 化：后端提供 schema（按 `request_type`）
- [ ] 前端按 schema 动态渲染表单 + 校验 + payload 构建（减少 hardcode）
- [ ] 管理端：表单 schema 的增删改查 + 版本管理（同一类型不同版本）
- [x] 工作流编辑器升级为“流程图视图”（节点/连线），并与 steps 双向同步（可选）

### 体验/运营能力（按需）

- [ ] 列表分页 + 高级筛选（状态/类型/时间范围/部门/关键字）
- [ ] 催办/超时（SLA）+ 站内提醒（可配置阈值）
- [ ] 报表：审批时长/通过率/流程分布（含导出）
- [ ] 通知渠道扩展：Webhook/邮件/企业微信（可选）

### 安全/部署（按需）

- [ ] 密码策略 + 登录限流 + 审计日志导出
- [ ] 配置化启动参数（端口、db_path、附件目录、管理员初始化等）
