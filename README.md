# OA (demo)

一个最小可用的 OA 示例：
- 前端：最简单的原生 HTML/CSS/JS（无框架）
- 后端：Python 标准库 HTTP Server + SQLite（无第三方依赖）
- Python 环境：建议用 `uv` 管理

## 运行（推荐 uv）

```powershell
uv run python -m oa_server
```

默认地址：`http://127.0.0.1:8000/`

首次启动会自动初始化 SQLite，并创建默认账号：
- 管理员：`admin / admin`
- 普通用户：`user / user`

登录后：
- 普通用户：在“发起申请”创建申请，在“我的申请”查看进度
- 管理员：在“我的待办”审批（demo 里 `user` 的直属领导默认指向 `admin`）

默认内置了一个简单审批流（可在后续迭代里做成可配置的，见 `DESIGN.md:1`）：
- `leave`（请假）：直属领导审批 → 结束
- `expense`（报销）：直属领导审批 → 财务审批（admin 角色）→ 结束
- `generic`（通用）：管理员审批 → 结束

如果你遇到本机环境不允许写入 `__pycache__` 的情况，可以临时用：
```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
```

## 运行（不用 uv）

```powershell
python -m oa_server
```

## 接口概览

- `POST /api/login`：登录
- `POST /api/logout`：退出
- `GET /api/me`：当前用户
- `GET /api/requests?scope=mine|all`：申请列表（all 仅 admin）
- `GET /api/requests/{id}`：申请详情（含流程/事件）
- `POST /api/requests`：创建申请（body 里带 `type`）
- `GET /api/inbox`：我的待办
- `POST /api/tasks/{id}/approve`：审批通过
- `POST /api/tasks/{id}/reject`：审批驳回
- `GET /api/users`：用户列表（admin）
- `POST /api/users/{id}`：更新用户 dept/manager（admin）
