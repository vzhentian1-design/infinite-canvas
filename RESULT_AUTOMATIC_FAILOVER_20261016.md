# 两款模型自动主备已上线

继承已上线 Canvas → 个人 New API rc44，不升级、不重建。当前正式员工入口仅有 **GPT Image 2.5 Flare**（默认）及 **GPT Image 2.5 Sunburst**。旧 Image 2、无后缀版保持隐藏；旧模型、渠道、三次齐东 Flare 真实生图/单参考/双参考及账单证据原位保留。

## 正式配置与故障处理

| Canvas 别名 | 齐东主渠道 / 优先级 | Packy 同款备用 / 优先级 | 真实模型 |
| --- | --- | --- | --- |
| canvas-image | 2 canvas-qidong-flare / 100 | 3 canvas-packy-flare / 10 | gpt-image-2.5-flare |
| canvas-image-sunburst | 4 canvas-qidong-sunburst / 100 | 5 canvas-packy-sunburst / 10 | gpt-image-2.5-sunburst |

Canvas 两款均只绑定原 New API 网关渠道，模型记录 ID 保留；供应商调度仅由 New API 负责。Canvas 不启用第二层付费重试，全局 RetryTimes=0 保持。两款渠道、冷却与恢复状态独立，不跨型号替换。

Owner 已批准主 180 秒、备 240 秒；Canvas 原总超时 480 秒保持。两款各冷却 300 秒，独立配置。冷却到期仅使齐东获得新业务请求的探测资格，实际成功才确认恢复；失败重新冷却。没有付费定时探活。

单任务最多两次供应商尝试，Packy 是最后一次。明确 401/发送前白名单可备用；已启用本项目限定的 5xx、408、429、超时/断线有限备用。先有请求号则只读核原账单，已确认原供应商扣费则不再发送；查不到账单不代表未受理。内容安全、400/403/422、已开始响应或调用方取消不盲目换商。结果未知的齐东请求可能继续完成并扣费，即使 Packy 已成功，也保留原未知尝试。主备同任务风险预留按币种分开为 CNY 0.03 + USD 3.557850，后者来自公开区间、不是供应商硬封顶；项目/Token 仍有限额，不自动充值。

Packy 按 low、768×1024、n=1，齐东不传 quality；不声称两家质量等价。原网关已有限制及 Canvas 既有多参考能力不作为本轮新增业务。未新增逐型号双参考付费验收。

## 真实验证：已批准 2 次，遇错停止后另批 1 次

本轮共 **3 次真实供应商发送、2 张成功图片**，都在独立 Canvas 数据库及 New API SQLite 副本中使用最终候选与真实供应商；没有额外生产付费探针。

| 尝试 | 结果 | 平台积分 | 可核供应商费用 |
| --- | --- | --- | --- |
| 齐东 Sunburst 单参考改图 | 成功，1086×1448；参考红杯改绿，主体保留 | 15000 | 请求号唯一关联，CNY 0.03 |
| Packy Flare 单参考改图（假主渠道失败后接管） | HTTP 400，拒绝 response_format，未返回图片；立即停测 | 0 | 待核实，不能把平台 0 积分当供应商免费 |
| Owner 另批的 Packy Flare 补测 | 修复参数后，同一任务假主渠道 401 → 真 Packy 成功，768×1024 绿杯 | 39753 | USD 扣费待核实，不虚构金额 |

齐东成功任务 `5c20d183-beae-48a4-87e7-15a04ac82de8`，网关 `202610160538486566849768268d9d6p16VYNpA`，供应商 `202610160538495962400658268d9d6oo68BFcH`。

Packy 初次失败任务 `9b5514f2-9390-43fa-a85b-a5f7065adfe8`；修复成功任务 `b0c8c32d-b686-421a-bc65-9b0b71e5c973`，网关 `202610160545409982737128268d9d614bMmq7g`。两次 Packy 场景的假齐东只由本地桩响应，没有真实齐东发送；不能称真实齐东生产故障。

真实故障暴露的修复仅作用于本项目 Packy 图片适配：JSON 生成及 multipart 编辑去掉其不接受的 response_format；齐东和其他项目保留原行为。修复已由单元测试、最终原生网关 24 场景免费回归及另批的 1 次真实请求共同验证。

复用证据：齐东 Flare 上阶段的生图、单参考、双参考及各 CNY 0.03；齐东 Sunburst 既有生成记录；Packy Flare 既有生成、Packy Sunburst 35 条历史 edits 消费记录。Packy Sunburst 的新网关实际生成未另行付费重测；复用历史编辑、相同适配及免费精确映射，保留这一证据边界。

## 计费与账单

每次尝试分别保留供应商、真实模型、两层请求编号、状态、New API 积分、独立币种估算及可核供应商扣费；失败和未知尝试也留存。齐东按张 CNY 0.03。Packy 使用自身 model_ratio=2.5、completion_ratio=6、image_ratio=1.6、image 分组倍率=5；个人网关专用计费身份合并 model_ratio=12.5，不给 Packy 配齐东固定三分钱，不影响其他模型价格。公开 USD 0.029400–3.557850 区间不是硬限价。39753 是实测平台积分，不能直接宣称为供应商已确认现金扣费。

**Packy 真实逐笔账单关联尚未完成。** Token 账单接口仍 record not found，网页登录样本无请求号，不能用时间接近的消费行或共享账户余额差额冒充唯一关联。失败调用后的余额观察未变，也不足以宣称其实际扣费为零。当前按 Owner 允许的边界保留待核实，未充值、未伪造金额。

Canvas 管理员详情列逐次账单；结算按请求替换快照，不累加轮询。网关批量请求号最多 25 个且仍按 token_id 隔离；Canvas 120 秒一轮批量同步，迟到账单 300 秒补查、最多回看 7 天，不放宽原网关限流。

## 验证与上线读回

- API 原套件 88 PASS / 1 个原 PG 并发项跳过；真实独立 PostgreSQL 另验批量两笔、迟到账单、重复查询抑制。API 编译、Web 类型检查/构建通过。
- 原生 rc44 最终修复网关 + 纯本地上游：24 场景通过，含两款独立主备、503 当前任务接管、冷却后新请求恢复、单/双参考、内容安全/参数拒绝、断线、超时及最多两次；新增拒绝 response_format 字段回归断言。真实 SQLite/MySQL8/PostgreSQL 的冷却恢复与 Token 日志隔离证据复用，未改数据库逻辑。
- 已发布镜像：API b0ad358fb014、Web 8823808ae9ec、个人网关 adbd3f91f50b；网关实现提交 5d297bd。只覆盖已上线 API 的 newapi-evidence.js / newapi-settlement.js、前端静态文件和个人网关二进制，保留原企业后端与 Compose 链。
- 正式登录会话的共用选择器读回仅两项，Flare 默认，切到 Sunburst 后恢复 Flare；模型/历史列表接口 200。该生产浏览器会话为管理员；独立真实验证则使用普通用户 API，实际选择两款模型并得到对应供应商结果。没有代替 Owner/员工宣称日常业务验收。
- 首页、Web→API /health、个人网关 /api/status 均 200；生产网关免费模型目录只返回两个别名，价格、超时、冷却、原 RetryTimes=0 与 Token 白名单读回通过。
- 412 日志 / 261 任务 / 227 图片、inflight=0；400 历史账单（272 候选 / 128 待核）保持。生产 Token 仍剩 455000 积分，未充值。rc39、Studio 试用 PG、Canvas PG/MinIO 的容器身份、配置、挂载、启动时间保持。所有本轮验收容器停止。

## 备份与回滚

本阶段 root 私有目录 `/opt/canvas-newapi-autofailover-20261016`，最终发布回执 `release-r2/completed.json`；新备份为 `release-r2/canvas-before.dump`、`newapi-before.db`、Canvas 模型/绑定和原生渠道/价格/Token 配置。原阶段备份、历史账单导入挂载和旧回滚容器保留。

前生产三个容器以 `-pre-autofailover-20261016-r2` 保留且停止。Compose 最后叠加 `compose.canvas-autofailover.json` / `compose.newapi-autofailover.json`。回滚脚本 `rollback_autofailover.py` 默认仅检查；明确执行加 `--execute-rollback`。先等活动任务为零并停提交，恢复本项目配置、回切原容器、重载 Nginx；不回灌旧数据库，不重置消耗积分，新增任务/图片/账单保留。

第一次发布因 SQLite 布尔值未转 JSON 布尔值被 Token API 拒绝；修正后又因旧 Nginx 缓存 API 地址导致健康检查误判。已实际回滚原配置/容器并恢复反代，业务数据未覆盖；最终 r2 改为先验 API 内部健康再换前端，成功上线。r2 备份与回滚容器默认检查 PASS，未为演练再停一次正式服务。失败过程及诊断保留在私有 release 目录。

可公开证据：`evidence/autofailover-20261016/published-safe.json`、`paid-result.json`、`protocol-fix-free.json`；不含密钥、会话或完整账户账单。

**未完成：** Packy 真实逐笔扣费关联、Owner/员工日常业务确认。没有待执行付费测试，不再扩大双参考或付费恢复验收。