# Canvas 历史账单接入

Owner 确认的目标：历史账单导入 Canvas，先在原后台逐笔查看。本次已发布到 [请求日志 → 历史账单](https://canvas.dongyuanhub.com/admin/logs?view=history)。图片渠道迁移、未来调用自动结算和收费验收未获本次授权，均未执行。

## 交付与证据边界

- 导入 400 条历史图片调用快照；12 条免费模型目录探测仍在原请求日志中，不计入图片账单。
- 272 条时间/模型/耗时双向唯一候选，128 条待核对。候选合计 Packy USD 4.532464、qidong CNY 6.000000；其中 25 条候选扣费为 0。没有一条被提升为已确认 Canvas 实付。供应商账户余额扣减也不等于银行现金成本。
- 每笔展示原请求/任务 ID、用户、渠道、模型、时间、状态、原金额、候选金额和币种，以及来源文件 SHA256/行号；保留原错误信息。生成/改图用途按保留的参考图记录推定，缺任务时显示未知。
- 343 条原成功请求金额为 0、其余为 NULL；不覆盖 request_logs.billed_amount、任务价格快照、图片费用或统计页总额，不把原有 0 当免费。
- 时间/模型/耗时匹配不是请求 ID 证据。结构化上游请求 ID 字段未保留；少量失败错误正文含请求号，后续可以继续核对。本次未完成供应商请求 ID 双向关联，待核记录金额保持空。
- Packy 的账户账单被多个项目共用；仅导入 Canvas 400 条记录和已唯一分配的候选，未把整账户消费归给 Canvas。

## 最小实现

管理员只读 GET `/api/admin/request-logs/history`。原列表 GET `/api/admin/request-logs` 同时按请求 ID 关联档案，直接显示候选金额、待核状态和账单详情，无需切换页面。历史账单独立视图还支持对账状态筛选与筛选合计，USD/CNY 独立计算到六位小数。未导入新请求保持原结算状态；档案损坏时原列表仍可读并明确提示关联失败。

档案是后端私有只读导入文件，独立于默认 30 天日志清理。通过导入 ID、SHA256、唯一请求 ID 与不重复供应商行校验防止重复归账；损坏时返回 503，未配置时显示尚未导入。未新增写接口，不经浏览器下发渠道凭据。历史账单不随“清空实时日志”删除。

服务器私有目录 `/opt/canvas-billing-import-20261016` 为 root 0700，导入文件和备份为 0600，API 只读挂载 `imports` 到 `/app/private-imports`。归档原件在同目录 `archive`，不作为前端静态文件。导入 SHA256：`da95ce331d82eb63785d4c7c67c9997f971a8819aa0d8a9c6a6cd0a63c8676b4`。

实际导入数据、供应商原账单及完整配置没有进入 Git。受保护本地证据位于 `D:\AI\codex项目\无限画布\canvas-billing-import-20261016`；原对账数据在相邻 `billing-reconciliation-20261016`。本地 ACL 限当前用户和 SYSTEM。

## 发布与验收

来源分支 `feat/canvas-historical-billing`，隔离 worktree 从 `upgrade/enterprise-v020` 的 `d767ae3` 起步；原 `phase2/safe-image-routing-costs` 未变，主备候选没有发布。

| 范围 | 结果 |
| --- | --- |
| API 实际文件差异 | 仅新增 `/app/dist/billing-history.js`、修改 `/app/dist/routes/admin-request-logs.js`；去掉历史读取及关联显示代码后，其余原日志路由编译结果与线上原模块完全一致 |
| 原 API 其余模块 | 按文件 SHA256 验证完全相同；worker、upstream、认证、数据库 schema、依赖及 migrations 未替换 |
| API 镜像 | `infinite-canvas-api:billing-history-listfix-20261016` / `06238696b70b85c24841ec6d40f32122730f511de8fd653d0b42bf3955e2f6ef` |
| 前端镜像 | `infinite-canvas:billing-history-listfix-20261016` / `04c38a60e1a68c0c10884b841dc5d1de7f7c7ee227ada77ec5570fc51a373a2e` |
| 数据保护 | 发布前新 pg_dump 330469 字节，pg_restore 目录校验通过；22 个业务表内容指纹全部相同，412 日志 / 261 任务 / 227 图片不变，inflight=0 |
| 其他运行系统 | rc44、rc39、Studio PostgreSQL、Canvas PG/MinIO 的容器身份、配置、启动时间及 Studio 主 PID 不变；原环境变量和端口保持 |
| 代码验证 | API 构建、前端类型检查和构建通过；5 项针对性测试通过，覆盖原列表 GET 返回候选/未知金额、按 ID 关联而不改原金额、零与未知、来源校验和管理员边界；角色/数据库测试使用隔离 mock，不冒充线上普通用户登录验收 |
| 线上验证 | health 200；匿名历史接口 401；管理员页面实际显示 400/272/128 和独立币种合计；候选和待核详情、128 条待核筛选通过；390px 窄屏无页面横向溢出，表格保留横向滚动 |
| 付费与迁移 | 模型请求新增 0、渠道/Key/权限/价格配置变化 0、Studio 改动 0、New API 图片迁移 0 |

备份：服务器目录 `backup-before` 内的新 PG dump、原容器完整配置及内容指纹；原阶段完整 MinIO/源码/镜像备份仍在 `/opt/canvas-upgrade-20261016/backup`。

原列表关联修复另有新备份 `backup-before-list-fix`、回滚容器 `canvas-migrated-api-pre-listfix-20261016` / `canvas-migrated-app-pre-listfix-20261016`。现场发布回执 `list-fix-result.json` 确认 22 个业务表、环境变量、端口、挂载和全部受保护服务不变。原 `/admin/logs` 近 7 天视图已实际核验：19:25:41 记录显示 USD 0.079180，19:18:57 显示 USD 0.051896，三条最新鉴权失败显示待核；原列表详情可查看来源。

回滚容器已停止保留：`canvas-migrated-api-pre-billing-20261016`、`canvas-migrated-app-pre-billing-20261016`；中间前端 `canvas-migrated-app-billing-r1` 也保留。回滚时只回切 API/app，保留账单目录及数据库；不要回滚或清空 PG/MinIO。应先检查没有新任务，再停止现容器、改名保留并启用对应旧容器，随后核 health/数据；回切不覆盖原记录。

Compose 应在原部署配置及前端 override 后叠加 `/opt/canvas-billing-import-20261016/compose.billing-override.json`，本次容器标签已记录配置链。不能从本分支全栈 compose build/up，因为分支其他后端源码不等于原线上 API。

## 停止与下一步

本次仅历史账单可视化导入完成，Owner 体验验收及候选扣费的请求 ID 确认仍待后续。未来自动计费应另行记录 Canvas 请求 ↔ 网关/供应商请求号、已结算金额与币种，再独立核实 New API 用户扣额和供应商扣费；不能依赖历史时间匹配永久自动结算。本阶段没有待执行写入或收费测试。
