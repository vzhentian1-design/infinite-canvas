# 当前生效：三模型、五渠道与管理计费收口

本阶段已按 Owner 最新口径发布：金额数值不换算，内部统一显示 USD；1:1 是展示规则，不是外汇汇率。后台保留供应商原币、原金额和核实状态。齐东平台价格保持 USD 0.03/张（15000 平台积分），供应商实际原币账单为 CNY 0.03/张；Packy 使用自己的动态用量计费，未套用齐东价格。

## 员工和管理员入口

- [员工生图工作台](https://canvas.dongyuanhub.com/image)：默认 GPT Image 2.5 Flare，也可选 GPT Image 2.5 Sunburst、GPT Image 2。员工不选供应商，添加参考图可改图。
- [模型广场](https://newapi.dongyuanhub.com/pricing)、[模型管理](https://newapi.dongyuanhub.com/models/metadata)：三款真实模型 ID 和用途/路由/价格说明；管理员可查看 Canvas 专用分组目录，未扩大普通账号或 Token 的调用权限。
- [渠道管理](https://newapi.dongyuanhub.com/channels)：按 canvas 筛选五条渠道，名称/真实模型/优先级/状态及备注对应下表。状态菜单可手动禁用、启用；手动禁用不由自动冷却恢复解除。不要点击付费渠道测试来代替启用操作。
- [New API 使用日志](https://newapi.dongyuanhub.com/usage-logs/common)：渠道列是实际所用供应商；详情增加员工、Canvas 任务号、两层请求号、逐次尝试、平台积分/金额、供应商原币账单和状态。旧记录未携带员工身份则显示未记录，不伪造历史。
- [Canvas 管理员请求日志](https://canvas.dongyuanhub.com/admin/logs)：原列表直接看实际供应商、自动备用、USD 展示及详细账单；[历史账单](https://canvas.dongyuanhub.com/admin/logs?view=history)继续保留。

| 员工模型 / 真实模型 ID | 齐东渠道 | Packy 渠道 | 规则 |
|---|---|---|---|
| GPT Image 2.5 Flare / gpt-image-2.5-flare | #2 canvas-qidong-flare，100 | #3 canvas-packy-flare，10 | 默认；同型号主备 |
| GPT Image 2.5 Sunburst / gpt-image-2.5-sunburst | #4 canvas-qidong-sunburst，100 | #5 canvas-packy-sunburst，10 | 同型号主备 |
| GPT Image 2 / gpt-image-2 | 无 | #6 canvas-packy-image2，100 | 仅 Packy，无备用、不跨型号 |

Canvas 三模型均唯一绑定原个人 New API 网关，修复 Sunburst 缺失 routing=newapi 标记，保留模型 UUID 和既有 Flare/Sunburst 内部别名以维持默认选择。New API 对外目录与模型白名单使用真实模型 ID，旧别名不再作为广场标题。其他项目 DeepSeek 模型、渠道、价格不改。

## 自动切换、费用证据和未完成项

沿用此前两款 2.5 的调度器、主180/备240秒、Canvas480秒、冷却300秒及最多两次尝试；New API 唯一换商，Canvas 单次发送、不重复付费重试。冷却结束仅标待业务确认，下一次真实请求成功后确认恢复，不付费探活。既有未知结果可能仍扣费的规则保持，不把失败平台积分0解释成供应商免费。

平台金额 = 平台积分 / 500000，独立于供应商实扣。Packy 三款按已核公开规则：模型2.5 × image分组5 = 专用模型倍率12.5；输出倍率6、图片输入倍率1.6，按实际用量动态结算。上述平台金额不是供应商已确认账单。全局 USDExchangeRate=7.3 保持，不改其他项目；本项目内部展示数值按1:1标USD。

供应商原币核实需精确请求号、模型、来源、金额/币种与证据摘要；齐东已具备可靠的逐请求原币账单接口。Packy 当前 cf.api.fan/api/log/token 返回404；www.packyapi.com/api/log/token 返回HTTP200但success=false、record not found。现有导出389行中271条图片消费（Image2 225、Flare6、Sunburst40）没有请求号列且会话ID为空，无法唯一绑定Canvas任务。共享余额变化、相近时间和模型金额不作为实扣证明。保留30秒只读结算同步：精确同步New API平台积分/金额，实际扣费明确待核实，后续需供应商提供可靠逐请求账单。400条历史档案原值保持，272候选/128待核，不覆盖、不重复计费。

本轮新增付费模型调用0。Image2沿用历史真实消费及本轮免费生成/多参考编辑/失败不跨模型验证，没有新增付费全链路图片或Owner业务验收。员工详情的可选供应商字段未扩展，管理员账单入口已完成。Studio将来可能接入New API仅记录方向，本轮不迁移。

## 代码、验证与发布保护

Canvas：仅 worker 透传员工身份、gateway请求头、结算证据及管理员日志/模型/统计页；企业API以现有镜像增量覆盖所需编译模块，未以普通main替换。移除旧统计页把未注明币种金额作为人民币汇总的误导展示，明细保留。New API：精确三模型路由约束、Image2仅Packy、日志身份和展示规则、原生详情中文字段及冷却状态说明；管理员模型广场目录补齐。无schema变更。

定向验证：Canvas结算6项和网关单次发送/员工身份2项；New API精确模型限制Go测试、原生日志UI8项与渠道状态已有测试；两前端类型检查/构建、API编译、GoLinux构建通过。最终原生网关8场景用假密钥/本地上游验证Image2生成/多参考编辑/失败不换型号、两2.5真实ID、同型号备用/冷却/恢复及逐次积分。免费模拟不冒充真实供应商质量或业务验收；此前24场景和三数据库证据复用，不重复大套测试。

生产412日志/261任务/227图片及6业务表指纹保持，400历史账单保持；生产Token余额455000、平台用户余额及消耗/错误日志未变。Canvas PG/MinIO、旧rc39与Studio试用PG容器身份/配置/挂载/启动时间保持。无待执行付费测试，免费验收容器停止。

私有发布证据 `/opt/canvas-management-closeout-20261016/release/`，含原始PG/SQLite备份、配置/容器快照、发布/价格纠正/展示与目录回执。初版错误地按7.3换算平台价格，Owner纠正后已恢复0.03，期间未新增消费；最终按Owner口径1:1展示。早期回执的0.004110与首次镜像仅为中间状态，不作为当前配置。

当前最终API镜像 `b549c23da987`，Web `03862fd73855`；最终网关 `bbdeeb47de90`（完整ID以同目录 `catalog-completed.json` 为准）。发布镜像标签分别为 `infinite-canvas-api:management-20261016`、`infinite-canvas:management-20261016`、`new-api:canvas-management-20261016`。

原三个容器以 `-pre-management-20261016` 保留；展示/目录修正前容器另保留，不覆盖旧阶段回滚。运行 `sudo python3 /opt/canvas-management-closeout-20261016/release.py` 只检查回滚资产；显式 `--rollback` 才回切原配置与容器。回滚不回灌业务库、不重置积分，不覆盖新任务；需先确认无进行中任务。当前阶段收口，不创建后继总控、不继续扩展平台。

---

以下是上一阶段记录，仅作历史；当前配置以上方为准。

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