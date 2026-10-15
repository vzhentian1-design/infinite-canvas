# 无限画布阶段一交接（2026-10-16）

## 当前结论与停止边界

正式入口 https://canvas.dongyuanhub.com/ 已部署企业适配的 v0.20.0 **前端**。后端、PostgreSQL、MinIO、渠道配置保持原运行版本；未将原作者纯前端方案替换企业系统。旧前端实际回切和再部署通过。阶段一生图验收未全部通过：唯一一次新生图返回供应商 401 Invalid token，已停止，改图未发送。没有开启自动付费重试、没有改 New API 配置、没有删除任何历史资产、没有修改东元 Studio 正式系统。

本分支 `upgrade/enterprise-v020` 已推送，未合并 main。后续不要把“前端已升级”写成“所有功能验收完成”。

## 真实来源与部署身份

| 项目 | 已核实身份 |
| --- | --- |
| 原服务器 checkout | `/opt/scienceworkbench/canvas`，origin 为 CodeWolffy/infinite-canvas，提交 `43407cc3d8b260bfb765a1331f714cbd67f5262c`，VERSION v0.18.0，另有 8 个工作区变更 |
| 原用户 Fork main | 原作者 v0.20.0 `3a6b64b602ad062b29fac66902ed18a7ef5fd9dc`，与线上企业分支不同 |
| 本次可追踪来源 | `6aa33c3` 保存线上工作区修改；`f6e6eff` 合入企业 v0.19.0；`08745294d0ce408ca4f889450f5032349884f2f3` 整合原作者 v0.20.0 前端变化 |
| 当前前端镜像 | `infinite-canvas:enterprise-v020-20261016-r2`，SHA256 `7e6d6c1575fb8add14fc4a72bafa1620ba4f960e74c78361803a7217e644ddf9` |
| 保持的 API 镜像 | SHA256 `8d467b14cf09d54a83b1ead0d9b0194b327cb9b000fb83c9a2df562969d7ad7f`，原容器未重建/重启 |
| 正式路径 | 主机 nginx HTTPS → `127.0.0.1:13001` → `canvas-migrated-app` nginx → 企业 API；Compose 项目 `canvas-migrated-20260919` |

整合保留企业账号、服务端加密密钥、API 图片请求、云端画布/历史/资产、快捷返修、批量逐张返修、员工默认模型和参数。没有照搬上游浏览器直连供应商及下发密钥的路径。v0.20.0 的画布聚焦、缩略图、重生成设置等已适配；视频/音频入口仍按企业能力限制。

**源码与运行时区别：** 分支含企业 v0.19.0 的后端源码，线上仍是原 API 镜像。本次只构建 web/dist 并覆盖旧前端镜像静态文件；不可用本分支直接全栈 `compose up --build` 冒充本次已验证发布。原服务器 checkout 和 WIP 保持原位；发布目录另在 `/opt/canvas-upgrade-20261016`。新镜像保留旧 hash 静态文件以支持已打开的旧客户端。初始候选因 Windows 打包文件权限出现 403，r2 对静态目录 `chmod -R a+rX` 后验证通过，初始候选未用于正式服务。

## 备份、保留和回滚

私有备份 `/opt/canvas-upgrade-20261016/backup/`：完整 pg_dump、MinIO 数据归档、原 checkout 含 Git/WIP/私有配置、原 app/API 镜像、容器配置及 SHA256SUMS。共约 996 MiB。私有源包和配置包含凭据，只在受保护目录保存，禁止提交仓库。Windows 已另存数据库及浏览器备份于本任务根目录 `backups/`（ACL 限本机用户和 SYSTEM）。

- 数据库恢复：在 `--network none`、tmpfs PG 容器实际 pg_restore；12 个核心表行数和内容指纹全部一致。原业务记录保留检查通过；浏览器上传测试新增一条具名 media，不删除。
- 个人设置：原 pg_dump 与线上语义对比 7 个用户、同一用户集合、changed_paths=[]；updated_at 的变化单独排除解释。浏览器原模型/质量/尺寸/张数在测试后恢复并核对。
- 浏览器：Canvas origin localStorage、sessionStorage、IndexedDB 导出可解析，约 3.39 MB；本地 IDB 文件另存。浏览器业务表为空，prompt_cache 有 7 条，不能把本地空表误写成服务器没有画布。下载文件在 Edge 中仍保留 `.crdownload` 状态，已复制完整字节并校验 JSON/PNG，不宣称浏览器下载管理器已最终完成。
- MinIO：归档可读、SHA 校验通过；未向正式卷执行恢复覆盖。不能把归档可读写成全量对象恢复演练。
- 回滚：停止新 app、临时更名；启动保留的旧容器到同一名称/端口，公网 health=ok，公网 index 与旧容器原文件逐字节一致；随后重新切回新 app，再次 health/index 一致。API、PG、MinIO、两个 New API、Studio PG 的容器 ID、启动时间、镜像和配置均不变。Docker Mounts 返回顺序不稳定导致第一次保护断言误报；按排列归一后独立校验全部一致。

目前旧容器为 `canvas-migrated-app-rollback-20261016`，镜像 SHA `6753f0800c9431cb26a8cefba5834c0b9386f06b0089d0c35dda7f303fefb987`。需要回滚时只操作前端：

```sh
sudo docker stop canvas-migrated-app
sudo docker rename canvas-migrated-app canvas-upgrade-held-for-investigation
sudo docker rename canvas-migrated-app-rollback-20261016 canvas-migrated-app
sudo docker start canvas-migrated-app
curl -fsS https://canvas.dongyuanhub.com/health
```

运行前确认临时名称未被占用，保留新旧两个容器及备份。正式 Compose 覆盖文件 `/opt/canvas-upgrade-20261016/compose.frontend-override.json` 指向 r2；原 Compose 单独执行可能回到旧镜像。后续发布必须显式包含对应覆盖并且仅操作 app。

## 验证证据与限制

| 验证 | 结果 |
| --- | --- |
| npm run typecheck / npm run build | PASS；构建有原有大 bundle 提示 |
| Bun 聚焦/模型选择/缩略图三个测试文件 | 15 PASS，0 FAIL，35 assertions |
| npm run test:node | 44 PASS / 4 FAIL；冻结的企业 v0.19.0 基线重跑为相同 4 FAIL，无新增失败 |
| 既有测试问题 | image-recovery 两处 loading/error fixture；request-session 的 localforage mock；session-isolation 预期网络失败的 unhandled rejection。本轮未扩大修复 |
| 正式工作台 UI | v0.20.0、旧历史 30 条可见、历史结果/参考图可读、实际文件选择上传成功、快捷与批量返修入口保留、模型/质量/尺寸/张数可操作 |
| 下载 | 实际点击历史原图下载，完整 PNG 1,521,603 B，1024×1024，SHA256 `68618e4c52a1e9f1ed461448b6338979ad413ec9a1ab21d469f8b6502b5aad5a`；显示缩略图为 768×768 WebP，二者已区分 |
| 唯一实际生图 | 2026-10-15 17:10:33 UTC，qidong、low、768×1024、n=1、无参考图；任务失败 HTTP401，见下方身份 |
| 真实改图 / 供应商质量 / 实际现金扣费 | 未验收；首请求失败后停止。没有请求 Packy，没有重试 |

生图 task `d418214e-613a-48ab-af5a-12b27827cc46`，request_log `c5b2f25e-edee-4d12-864b-07e517c68c29`，供应商 request id `202610151710337498450728268d9d6qILNmZpO`。同 task 仅 1 条调用记录，request_logs 总数从 409 到 410，任务 failed，无 queued/running。错误 `Invalid token`，billed_amount=NULL；NULL 不能当作现金 0 元。

Owner 提供齐东 ¥0.03/张；按原验收范围限定最多 2 次、预计 ¥0.06、首失败停止。实际只发 1 次，改图 0 次。当前齐东登录账号当日请求号检索未找到匹配账单，模型广场搜索 gpt-image-2 为 0 结果；令牌列表有 3 个禁用、1 个启用，未揭示或更换密钥，未建立服务器密钥与其中某条的匹配。401 鉴权失败已证实，具体失效原因及实际扣费 UNKNOWN。

Packy 当前公开模型详情将 gpt-image-2 / 2.5-flare / 2.5-sunburst 列为 image 分组按次计费、范围 $0.029–$3.558、显示 7.2 折。这与“按输入输出”旧描述不同；详情未给出本次参数对应的确定账单，不能用区间、折扣或账户余额变化伪造逐请求现金成本。未发 Packy 验收调用。

本机原始证据在任务根目录 `evidence/`：构建/测试日志、rollback-rehearsal.log、protected-check.txt、数据指纹、preference-semantic-check.json、browser-preservation.json、paid-validation-result.txt、供应商定价及检索文本、workbench-v020.jpg、generation-failure-v020.jpg。业务截图、数据库、账户余额及历史内容不上传公开仓库；发布摘要见本文件和 `ASSET_INVENTORY_20261016.md`。

## 真实调用链、503 与主备最小方案

当前链路是 **浏览器 → Canvas 企业 API/worker → Canvas 自己数据库的 channel → 齐东或 Packy**；不经过自建的 new-api-personal 或 sw-new-api-rc39。

| Canvas 渠道 | 当前实际配置（未更改） |
| --- | --- |
| qidong | active，`https://api.qidong.autos/v1`，upstream `gpt-image-2-qidong` |
| Packy | active，`https://cf.api.fan/v1`，gpt-image-2 / 2.5-flare / 2.5-sunburst |

两渠道 timeout=480000ms、maxConcurrency=4、cooldown=120s；所有现有绑定 priority=0，每个模型仅一条渠道。UI 两个模型是手动选择，**不是主备自动故障转移**。齐东 503 是既有真实记录，例如 `946bbf06-c39c-4f97-93bd-f538240538bb`（2026-10-15 05:43:11 UTC）及另外两次 503。现有调度器可冷却故障渠道并尝试已绑定的后续候选，但当前没有第二候选；队列 retryLimit=0，不能把“active/冷却已到期”当作真实恢复。最新验收是 401，不能继续用昨日 503 解释。

阶段二最小任务（待裁决）：先安全核对齐东凭据/当前售卖模型，再完成受限生图与改图验收；选定 **只用一个路由层**。最快路径复用 Canvas 模型多渠道优先级（中等配置/协议映射工作），但 qidong upstream 名称和 Packy gpt-image-2 不同，需显式映射和受控验证。若统一通过 New API，则先为独立 rc44 配置隔离的图片 token/分组和主备映射，再让 Canvas 仅绑定这个网关；不要动 rc39 或 Studio。迁移中等工作量。默认仍 0 自动重试；503/超时不能证明上游未受理，自动换商可能双扣，需预算、幂等与 UNKNOWN 处理后单独批准。

## New API 费用接口与阶段三

独立 New API rc44 有原生渠道优先级/权重、降级重试、自动禁用与测试恢复代码，但当前只有 DeepSeek 文本渠道，RetryTimes=0。rc44 默认重试状态范围含 500–503，不含 504/524；自动禁用默认状态为 401，功能开关默认 false。渠道测试会结算用量，不是免费探活。与现在线上版本对应的代码是 tag `v1.0.0-rc.44` / `633b4c5b190dc1af99a2814391354d86948e7943`，不能用维护 Fork main 的较新实现充当当前行为。

逐请求平台计费接口可用：`GET /api/log/`（管理）、`/api/log/self`（用户）、`/api/log/token`（TokenAuthReadOnly，限最近条数）。已用既有管理员登录 GET /api/log/ 返回 HTTP200/success，并按现存 request_id 筛选得到唯一一条，随后退出检查会话，无生成调用。字段含 request_id、quota；quota_per_unit=500000，显示换算 usd_exchange_rate=7.3。

阶段三最小任务（待裁决）：服务端保存 Canvas task_id ↔ New API 响应请求号 ↔ 日志记录身份，异步读取该 token 的已结算 quota，前端先显示“待结算/已结算/未知”。三个概念独立：①供应商实际现金扣费（需供应商账单或可靠成本接口）；②New API 对平台用户扣减 quota（已有接口）；③按模型价/汇率估算金额（只能标估算）。现有 Canvas generated_images.billedAmount 来源 task.priceSnapshot，不能改标签冒充真实成本。管理员密钥、全站日志不得下发浏览器；token 接口的最近记录窗口需及时同步。账单关联及显示为中等开发量；供应商现金自动对账仍待核实。

## Notion 与交付责任

[Canvas 项目入口](https://app.notion.com/p/3face9f11b9b81bf9b80d5ec21f22085) · [New API 项目入口](https://app.notion.com/p/3face9f11b9b8154bcdfcf48c824f33e)。统一总目录复用既有「项目」数据库，以每项目一个入口串联代码/域名/版本/里程碑/证据/遗留/下一步；已有「东元 Studio｜项目入口」保留原位链接，未重建档案。资产盘点与清理建议见同仓库 `ASSET_INVENTORY_20261016.md`；未获得删除授权，不执行清理。阶段一在此停止，后续路线及新的付费验收由 Owner 裁决。
