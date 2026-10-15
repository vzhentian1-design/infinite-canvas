# 第二阶段结果：安全候选完成，供应商模型阻塞

STATUS = HOLD_PROVIDER_MODEL_AND_COST_BOUNDARY
CURRENT_STAGE = PHASE2_LOCAL_CANDIDATE
CODE_COMMIT = fad1dfe6fac1cda51dde3348a9b7696f9ec98993
CODE_TREE = aad056dae20dc51e8c0a94f9480b87f3d0a9bf8b
BASELINE = d767ae3bfebd9cda1ba3eedd58eddaa3fdc3eec4
BRANCH = phase2/safe-image-routing-costs
DEPLOYED = NO
ASSISTANT_PAID_IMAGE_SENDS = 0
CONTROL_PLANE_DOCS_NETWORK = 0
BUSINESS_EXECUTION_NETWORK = GitHub / Notion / existing SSH / provider documentation and free GET model catalogs

## 目录与基线

- 本机项目入口 `D:\AI\codex项目\无限画布` 是既有资产目录，本身无 `.git`；源码位于其 `infinite-canvas` 子目录。未 clone、未 init、未覆盖修改。
- `infinite-canvas` 接管时为干净的 `upgrade/enterprise-v020`，origin 为 `https://github.com/vzhentian1-design/infinite-canvas.git`，本地及远端均为基线 d767ae3。已有 main 为原作者纯前端 v0.20.0 的 3a6b64b，不能作为本阶段施工起点。
- `enterprise-reference` 为 CodeWolffy 企业来源参考仓；`new-api` 为 `docs/canvas-verification-20261016` 文档核验分支。两者未修改。父目录的 scripts/evidence/backups 已有第一阶段产物，继续复用。
- 从企业升级基线创建本施工分支。沿用上一阶段提交身份 Dongyuan Upgrade，仅在 commit 命令内指定；没有更改全局 Git 配置。
- 现有 SSH `scienceworkbench-current` 可用。服务器 `/opt/scienceworkbench/canvas` 仍为 43407cc + 原 WIP，未修改。发布目录 `/opt/canvas-upgrade-20261016` 与完整备份保留。

## A：401 已定位，当前阻塞已变为 403 / 空目录

1. 线上 qidong 渠道仍为 OpenAI 协议、`https://api.qidong.autos/v1`、上游 `gpt-image-2-qidong`。加密密钥可在原 API 运行环境解密，未输出或导出密钥。
2. 只比较脱敏首尾，服务器密钥匹配齐东页面 `qidoong生图` 令牌。接管时它已禁用；页面显示永不过期、无限配额、无限制模型/IP、生图分组。免费 GET `/v1/models` 返回 401 Invalid token。脱敏匹配不是全密钥逐字节比对；结合 Owner 启用后的行为变化，支持该禁用为 401 的原因。
3. Owner 亲自启用了原令牌。随后免费 GET `/v1/models` 为 200 / 空列表，按当前文档 GET `/v1/models?type=image` 也为 200 / `success=true,data=[]`。没有替换密钥，未保存新令牌。
4. Owner 自行发起的实际 Canvas 请求于北京时间 2026-10-16 02:39:52 返回 **403：This token has no access to model gpt-image-2-qidong**。身份：task `b9f59fd4-d0de-44ed-98be-10c5882a6b9c`，log `ab76fd30-8270-453f-9b73-9943f8670672`，供应商请求号 `202610151839524152353608268d9d6Str9An0R`。不能将此写成生图成功或仍是 401。
5. 当前模型广场未找到旧 GPT Image 模型；图片类别显示 6 个，已查看卡片包括 Gemini 3 / 3.1 与 Grok。新令牌表单仍提供生图分组，但没有证据表明新建同分组令牌能恢复旧 GPT Image，因此未为了重复失败创建新凭据。未确认现行可调用的 ¥0.03 GPT Image 替代项。
6. **谁禁用、何时禁用、旧模型何时撤下、是否永久下架均未查明。** 公告通知仅有充值说明，时间线显示暂无系统公告。不能认定是供应商主动封禁账户。

已查看的供应商历史日志中，2026-10-14 19:26:38（北京时间）有 `qidoong生图 / gpt-image-2-qidong` 成功、账户扣减 ¥0.03 的样本；10 月 15 日白天多次 503。Canvas 503 如 log `946bbf06-c39c-4f97-93bd-f538240538bb`，开始于 2026-10-15 13:43:11 北京时间。503、禁用导致的 401、重新启用后的 403 必须分别解释。供应商旧成功样本与 Canvas 时间相近，但缺少唯一请求号关联，不能给某张历史图补记实际现金成本。

当前文档 [统一媒体 API](https://api.qidong.autos/model-docs/unified-media-api.html) 明确：目录按当前 Token 可用模型返回；图片生成和带参考图编辑统一走 `POST /v1/images/generations`；旧 `images/edits` 暂兼容；模型目录决定输入类型、价格、尺寸等。当前广场和文档是核验时快照，不保证恢复时间。

## B：Canvas 主备安全代码候选

继续复用企业 API、原 model_channels、优先级、加权候选、并发槽位、渠道冷却和任务队列，不接入 New API。

| 情况 | 新候选行为 |
| --- | --- |
| 尚未发送的渠道并发槽位不可用 | 可选择下一候选，未发送原供应商请求 |
| HTTP401、没有内容拒绝标记 | 允许最多主备各一次；整体最多 2 次 action，无循环重试 |
| HTTP403 权限问题、明确内容/参数拒绝 | 停止该任务，不自动换商 |
| HTTP429、503及其他5xx、超时、断连、异常/空响应 | 停止；生成结果或费用可能未知，不自动换商 |
| 重启时仍在 running 的图片任务 | 标记 failed + worker_restart_unknown，不重新排队发送 |
| 当前或既往 attempt 结果未知 | 既有 retry 接口返回409，先核对供应商，再决定是否新建任务 |
| request_logs 无法写入 | 未发送图片请求即停止，避免无记录的付费调用 |

主渠道冷却到期后仍按原优先级参与**新任务**，没有额外付费健康探测。模拟恢复不等于主渠道真实恢复。未修改现有 480000ms 超时、并发4、故障冷却120s及原鉴权冷却规则。文本调度保持原逻辑。

配置草案是复用员工既有逻辑模型 ID `787484ab-3786-4e00-8a87-4037fe4eea08`，显示名可统一为 GPT Image 2：qidong priority100、Packy priority0、分别映射已验明的上游名。**草案未执行，Packy备用未绑定或启用，员工模型列表未隐藏或改名。** 现有 qidong 模型可用性/协议未通过；Packy费用边界未获具体裁决，不能启用自动转移。

Packy 免费 `/v1/models` 检查HTTP200，当前 Token 列出 gpt-image-2、gpt-image-2.5-flare、gpt-image-2.5-sunburst。Canvas 现有实现对两渠道发送 OpenAI 图片生成；编辑使用 multipart、重复 image 字段、n=1。768×1024 / low / 多参考图保留仅已做模拟序列化验证，**没有声称两个供应商真实都接受**。当前齐东新模型文档的统一路径需单独受控验收，不能将 Gemini/Grok 改名冒充 GPT Image。

## C：费用记录候选与边界

- 增量迁移 0014 仅为现有 request_logs 增加 `upstream_request_id` 和 `estimate_snapshot`；未在正式库执行。
- 请求开始时按实际渠道保存平台配置估算快照；不把 qidong 报价套给 Packy。估算配置沿用 models.config 的 `channelEstimates[channelId] = {amount: "0.03", currency: "CNY"}` 格式，仅为**示例**。缺失/无效报价为 null。没有把示例 ¥0.03 写入正式模型。
- 请求号从响应头取得；错误体中明确的 request id 可作为回退。已有历史记录不猜测回填。
- 后台每 attempt 可查看实际渠道、上游模型、任务号、供应商请求号、生成结果和渠道估算；金额明确标“估算”。供应商实际扣费字段保持 null、结算状态 unknown，展示“供应商扣费未知”。
- 老 `billed_amount` 字段的价格快照/0 记录保留，不将其解释为供应商现金成本。缺失历史报价也不会变成零价。
- 后台原用户、日期、渠道筛选保留；员工费用汇总、长期审计留存和供应商自动账单关联未实现。现有请求日志30天保留规则未改，因此不能承诺无限历史费用账本。
- Packy账户样本扣减与输入/输出token相关，第一阶段证据继续有效；充值实付折算、单图报价公式和可靠账单关联仍未查明。价格卡、账户扣减、平台估算和现金支出互相独立。

## 验证与运行状态

| 检查 | 结果与证据 |
| --- | --- |
| API build | PASS，npm run build |
| API全部现有及新增测试 | 78项：77 PASS / 0 FAIL / 1 SKIP；缺 TEST_DATABASE_URL 的真实PG并发测试跳过，PGlite不冒充实库验证；`evidence/phase2/api-tests.txt` |
| 前端typecheck/build | PASS，保留原大bundle警告；同目录 web-typecheck.txt / web-build.txt |
| 新增模拟能力 | safe-image-routing.test.mjs：错误分类/发送次数/恢复优先级/渠道估算隔离/多参考图/请求号；lifecycle：日志不可写不发送、重启不重放、未知重试409、估算不冒充现金 |
| 本地真实页面组件 | Vite独立loopback预览、全部API使用模拟数据；浏览器检查“估算 CNY 0.03”“供应商扣费未知”“结果未知，请先核对再重试”，截图目视布局正常；不代表线上或Provider通过 |
| Impeccable范围检查 | detector返回[]；没有重设计现有后台 |
| 正式入口 | health=ok；仍为第一阶段前端镜像7e6d6c1575fb / 原API镜像8d467b14cf09 |
| 服务器保护 | 本轮无服务器写入/部署/重启；API/PG/MinIO/两个New API/Studio PG的镜像和启动时间仍为接管身份；旧前端回滚容器与备份未动 |

最终只读查询 request_logs=412、queued/running=0；比接管时411增加的是Owner 02:39的403测试，不是本助手发送。原始只读回执及供应商页面研究存于父目录 evidence/phase2-*，不公开业务账户截图/历史内容。工程测试日志仅含模拟数据，可随分支发布。

## 企业版有限历史核查

- 企业改造提交 `2037cf6d0aacf4167636c2880feffd1335dfe27a`，作者Wolffy，2026-08-21 16:20:16 +08，说明“改造为可供企业内部使用的项目”；新增API、账号/会话、渠道加密、PostgreSQL、MinIO与任务队列。其父提交9414048的README指向 basketikun/infinite-canvas，证明该历史树的公开上游指向；未另考古私下开发过程。
- 后续可见渠道/审核拒绝、调度冷却与并发、管理员request_logs、队列幂等与媒体一致性等提交。当前服务器源为43407cc + WIP。
- 当前API容器启动于2026-09-19，匹配迁移部署目录和Compose项目。第一阶段6aa33c3保存线上WIP，f6e6eff整合企业v0.19，0874529整合原作者v0.20前端，d767ae3为交接修订。实际前端回滚证据沿用第一阶段，未重复演练。
- CodeWolffy首次部署日期、全部历史服务器变更、供应商何人禁用令牌及模型撤下时间：未查明。

## 停止边界与最小下一步

1. 先取得齐东当前可用的 GPT Image 模型/Token权限与可验证价格，或由Owner裁决更换同型号主渠道。既有令牌鉴权恢复不等于模型恢复，不继续向已拒绝的旧名付费尝试。
2. 新的受限验收授权已由Owner“自己试试”给出，本助手已声明采用已核实¥0.03模型、最多生图1次+成功后改图1次、预计≤¥0.06、首失败停止。**现行同价模型未确认，预算未使用；不得挪去更贵模型或Packy。** 有可用模型后先免费查目录，再用无敏感内容做1张，核对请求号/账单后才做1次双参考图编辑；不自动重试。
3. 对Packy取得单次费用规则/上限后，再由Owner明确裁决备用启用；先用本候选完成实库迁移与发布验收。自动跨供应商转移不因已有原理测试而获准。
4. 本轮没有部署版本，因此没有生产回滚动作。后续发布须冻结新commit，先备份PG/配置/当前app和API镜像、确认无inflight，再仅更新Canvas；禁止直接全栈compose --build。保留旧app/API容器或可恢复镜像，迁移为兼容性加列，回滚先恢复应用镜像，不删新列、不还原覆盖业务数据。第一阶段回滚方法仍见HANDOFF历史段。

当前代码候选已降低可实现的重复发送风险，但**线上仍是旧API**，其重启重新排队等既有风险尚未被本候选消除；未启用新主备，不能宣称重复扣费风险已在线上解决。达到准确供应商阻塞后收口，不扩大为新的计费平台或更换模型工程。
