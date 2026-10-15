import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, App, Button, DatePicker, Drawer, Segmented, Select, Table, Tooltip } from "antd";
import { useSearchParams } from "react-router-dom";
import type { TableColumnsType } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { RefreshCw, Trash2 } from "lucide-react";

import { useCopyText } from "@/hooks/use-copy-text";
import { clearAdminRequestLogs, getAdminChannels, getAdminModels, getAdminRequestLogs, type RequestLog } from "@/services/api/admin-platform";
import { getAdminUsers } from "@/services/api/admin-users";

type Filters = { range: [Dayjs, Dayjs] | null; userId?: string; modelId?: string; channelId?: string; type?: RequestLog["type"]; status?: RequestLog["status"]; reconciliation?: "candidate" | "unknown" };
const typeLabels = { image: "生图", text: "文本", probe: "探测" } as const;
const statusLabels = { running: "运行中", succeeded: "成功", failed: "错误" } as const;

export default function AdminRequestLogsPage() {
    const { message, modal } = App.useApp();
    const copyText = useCopyText();
    const queryClient = useQueryClient();
    const [searchParams, setSearchParams] = useSearchParams();
    const history = searchParams.get("view") === "history";
    const [detail, setDetail] = useState<RequestLog | null>(null);
    const [filters, setFilters] = useState<Filters>(() => ({ range: history ? null : [dayjs().startOf("day"), dayjs()] }));
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);
    const [preset, setPreset] = useState<number | null>(history ? null : 1);
    const usersQuery = useQuery({ queryKey: ["admin", "users"], queryFn: getAdminUsers });
    const modelsQuery = useQuery({ queryKey: ["admin", "models"], queryFn: getAdminModels });
    const channelsQuery = useQuery({ queryKey: ["admin", "channels"], queryFn: getAdminChannels });
    const logsQuery = useQuery({
        queryKey: ["admin", "request-logs", history, filters.range?.[0].toISOString(), filters.range?.[1].toISOString(), filters.userId, filters.modelId, filters.channelId, filters.type, filters.status, filters.reconciliation, page, pageSize],
        queryFn: () => getAdminRequestLogs({
            from: filters.range?.[0].toISOString(),
            to: filters.range?.[1].toISOString(),
            userId: filters.userId,
            modelId: filters.modelId,
            channelId: filters.channelId,
            type: filters.type,
            status: filters.status,
            reconciliation: filters.reconciliation,
            limit: pageSize,
            offset: (page - 1) * pageSize,
        }, history),
        refetchInterval: (query) => (query.state.data?.logs.some((log) => log.status === "running") ? 5000 : false),
    });
    const clearMutation = useMutation({
        mutationFn: clearAdminRequestLogs,
        onSuccess: (deleted) => { void queryClient.invalidateQueries({ queryKey: ["admin", "request-logs"] }); message.success(`已清空 ${deleted} 条日志`); },
        onError: (error: Error) => message.error(error.message || "操作失败"),
    });
    const setFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => { setPage(1); if (key === "range") setPreset(null); setFilters((current) => ({ ...current, [key]: value })); };

    const columns: TableColumnsType<RequestLog> = [
        { title: "时间", key: "time", width: 190, render: (_, log) => <div><div>{dayjs(log.startedAt).format("YYYY-MM-DD HH:mm:ss")}</div><div className={log.status === "succeeded" ? "text-emerald-600" : log.status === "failed" ? "text-red-500" : "text-stone-400"}>{statusLabels[log.status]}</div></div> },
        { title: "用户", key: "user", width: 130, ellipsis: true, render: (_, log) => log.userDisplayName ? <span title={`@${log.username || ""}`}>{log.userDisplayName}</span> : <span className="text-stone-400">—</span> },
        { title: "类型", dataIndex: "type", width: 76, render: (value: RequestLog["type"]) => value === "probe" ? <span className="text-stone-400">{typeLabels[value]}</span> : typeLabels[value] },
        { title: "模型 / 渠道", key: "model", width: 250, ellipsis: true, render: (_, log) => <div><div className="truncate" title={log.modelDisplayNameSnapshot || undefined}>{log.modelDisplayNameSnapshot || <span className="text-stone-400">—</span>}</div><div className="truncate text-xs text-stone-500" title={log.upstreamModel || undefined}>{[log.channelNameSnapshot, log.upstreamModel].filter(Boolean).join(" · ") || "—"}</div></div> },
        { title: "HTTP", dataIndex: "httpStatus", width: 70, render: (value: number | null, log) => value ? <span className={log.status === "failed" ? "text-red-500" : ""}>{value}</span> : <span className="text-stone-300 dark:text-stone-600">—</span> },
        { title: history ? "供应商扣费（待核）" : "费用", key: "cost", width: history ? 200 : 110, render: (_, log) => log.historicalBilling ? <div className="tabular-nums"><div>{candidateAmount(log)}</div><div className="text-xs text-stone-500">{log.historicalBilling.status === "candidate" ? "候选关联 · 实付未确认" : "缺少唯一账单关联"}</div></div> : log.billedAmount != null && Number(log.billedAmount) > 0 ? `¥${Number(log.billedAmount).toFixed(2)}` : <span className="text-amber-600">成本待结算</span> },
        { title: "耗时", key: "duration", width: 130, render: (_, log) => <div className="flex items-center gap-2">{log.durationMs != null && <span className={`h-4 w-[3px] rounded-full ${log.status === "failed" ? "bg-red-400" : "bg-emerald-500"}`} />}<span className={log.durationMs == null ? "text-stone-300 dark:text-stone-600" : ""}>{log.durationMs == null ? "—" : `${(log.durationMs / 1000).toFixed(1)}s`}</span></div> },
        {
            title: "详情",
            key: "detail",
            render: (_, log) => {
                if (log.historicalBilling) return <Button type="link" size="small" onClick={() => setDetail(log)}>查看账单</Button>;
                const summary = [log.errorCategory, log.httpStatus ? `HTTP ${log.httpStatus}` : "", log.errorMessage].filter(Boolean).join(" · ");
                return summary ? (
                    <Tooltip title="点击复制详情"><div className="max-w-[420px] cursor-pointer truncate hover:text-stone-950 dark:hover:text-stone-100" onClick={() => copyText(logDetail(log), "请求详情已复制")}>{summary}</div></Tooltip>
                ) : <span className="text-stone-300 dark:text-stone-600">—</span>;
            },
        },
    ];

    return (
        <div className="w-full px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            <div className="flex flex-wrap items-end justify-between gap-4">
                <div><h1 className="text-2xl font-semibold tracking-[-0.03em] text-stone-950 dark:text-stone-100">请求日志</h1><p className="mt-1 text-sm text-stone-500">{history ? "逐笔查看导入的历史图片调用和供应商扣费依据；档案独立保留。" : "记录每次上游模型调用，含失败重试与手动探测；默认保留 30 天。"}</p></div>
                <div className="flex gap-2">
                    <Button icon={<RefreshCw className="size-4" />} onClick={() => void logsQuery.refetch()}>刷新</Button>
                    {!history && <Button danger icon={<Trash2 className="size-4" />} loading={clearMutation.isPending} onClick={() => modal.confirm({ title: "清空全部请求日志？", content: "将删除所有历史日志，正在运行的记录不受影响。", okText: "清空", cancelText: "取消", okButtonProps: { danger: true }, onOk: () => clearMutation.mutateAsync() })}>清空日志</Button>}
                </div>
            </div>
            <Segmented className="mt-5" value={history ? "history" : "live"} options={[{ label: "实时请求", value: "live" }, { label: "历史账单", value: "history" }]} onChange={(value) => { const nextHistory = value === "history"; setSearchParams(nextHistory ? { view: "history" } : {}, { replace: true }); setFilters({ range: nextHistory ? null : [dayjs().startOf("day"), dayjs()] }); setPreset(nextHistory ? null : 1); setPage(1); }} />
            {logsQuery.isError && <Alert className="mt-4" type="error" showIcon title="账单读取失败" description={logsQuery.error.message} action={<Button onClick={() => void logsQuery.refetch()}>重试</Button>} />}
            {history && logsQuery.data?.history && <div className="mt-4 space-y-1 text-sm text-stone-600 dark:text-stone-300">
                <p>已导入 {logsQuery.data.history.importedCount} 条图片调用 · 当前筛选：候选关联 {logsQuery.data.history.candidateCount} 条，待核对 {logsQuery.data.history.unknownCount} 条。</p>
                <p className="tabular-nums">候选扣费合计：USD {logsQuery.data.history.candidateTotals.USD} / CNY {logsQuery.data.history.candidateTotals.CNY}。币种分别统计，均未确认为 Canvas 实付。</p>
                <p>匹配依据：模型、结束时间与耗时；尚未完成上游请求 ID 双向核对。原费用字段未改写，0 不代表免费。快照截至 {dayjs(logsQuery.data.history.snapshotAt).format("YYYY-MM-DD HH:mm:ss")}。</p>
            </div>}
            {history && logsQuery.data?.history === null && <Alert className="mt-4" type="info" title="尚未导入历史账单" />}
            <div className="mt-6 flex flex-wrap gap-3 rounded-xl border border-stone-200 bg-background p-4 dark:border-stone-800">
                <Segmented value={preset} options={[{ label: "今天", value: 1 }, { label: "近 7 天", value: 7 }, { label: "近 30 天", value: 30 }]} onChange={(value) => { const days = Number(value); setPreset(days); setPage(1); setFilters((current) => ({ ...current, range: [dayjs().subtract(days - 1, "day").startOf("day"), dayjs()] })); }} />
                <DatePicker.RangePicker value={filters.range} allowClear showTime={{ format: "HH:mm" }} onChange={(range) => setFilter("range", range as [Dayjs, Dayjs] | null)} />
                <Select allowClear placeholder="全部用户" className="min-w-36" value={filters.userId} onChange={(value) => setFilter("userId", value)} options={(usersQuery.data || []).map((user) => ({ value: user.id, label: user.displayName }))} />
                <Select allowClear placeholder="全部模型" className="min-w-40" value={filters.modelId} onChange={(value) => setFilter("modelId", value)} options={(modelsQuery.data || []).map((model) => ({ value: model.id, label: model.displayName }))} />
                <Select allowClear placeholder="全部渠道" className="min-w-36" value={filters.channelId} onChange={(value) => setFilter("channelId", value)} options={(channelsQuery.data || []).map((channel) => ({ value: channel.id, label: channel.name }))} />
                {!history && <Select allowClear placeholder="全部类型" className="min-w-28" value={filters.type} onChange={(value) => setFilter("type", value as RequestLog["type"])} options={Object.entries(typeLabels).map(([value, label]) => ({ value, label }))} />}
                <Select allowClear placeholder="全部状态" className="min-w-28" value={filters.status} onChange={(value) => setFilter("status", value as RequestLog["status"])} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} />
                {history && <Select allowClear placeholder="全部对账状态" className="min-w-36" value={filters.reconciliation} onChange={(value) => setFilter("reconciliation", value)} options={[{ value: "candidate", label: "候选关联" }, { value: "unknown", label: "待核对" }]} />}
            </div>
            <Drawer title="历史请求账单" open={detail !== null} onClose={() => setDetail(null)} size="large" extra={detail && <Button onClick={() => copyText(logDetail(detail), "账单详情已复制")}>复制详情</Button>}>
                {detail && <div className="whitespace-pre-wrap break-words text-sm leading-7">{logDetail(detail)}</div>}
            </Drawer>
            <div className="mt-5 overflow-hidden rounded-xl border border-stone-200 bg-background dark:border-stone-800">
                <Table<RequestLog>
                    rowKey="id"
                    size="small"
                    columns={columns}
                    dataSource={logsQuery.data?.logs || []}
                    loading={logsQuery.isLoading}
                    scroll={{ x: 1160 }}
                    pagination={{ current: page, pageSize, total: logsQuery.data?.total || 0, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50, 100], onChange: (page, size) => { setPage(page); setPageSize(size); }, showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条 / 共 ${total} 条` }}
                />
            </div>
        </div>
    );
}

function candidateAmount(log: RequestLog) {
    const b = log.historicalBilling;
    return b?.status === "candidate" && b.amount !== null ? `${b.currency} ${b.amount}` : "待核对";
}

function logDetail(log: RequestLog) {
    return [
        `时间：${dayjs(log.startedAt).format("YYYY-MM-DD HH:mm:ss")}`,
        `请求 ID：${log.id}`,
        `任务 ID：${log.taskId || "未保留"}`,
        `状态：${statusLabels[log.status]}`,
        `用户：${log.userDisplayName || "—"}${log.username ? ` (@${log.username})` : ""}`,
        `类型：${typeLabels[log.type]}`,
        `模型：${log.modelDisplayNameSnapshot || "—"}${log.modelNameSnapshot ? ` (${log.modelNameSnapshot})` : ""}`,
        `渠道：${log.channelNameSnapshot || "—"}`,
        `上游模型：${log.upstreamModel || "—"}`,
        `HTTP：${log.httpStatus ?? "—"}`,
        `耗时：${log.durationMs == null ? "—" : `${(log.durationMs / 1000).toFixed(1)}s`}`,
        ...(log.historicalBilling ? [
            `供应商扣费候选：${candidateAmount(log)}`,
            "已确认实付：未知（尚未完成上游请求 ID 双向核对，候选扣费不等于已确认实付）",
            `原费用记录：${log.billedAmount ?? "空"}（币种未注明；0 不代表免费）`,
            `用途（按参考图记录推定）：${({ generation: "生成", edit: "改图", image_operation_unknown_task_missing: "未知，原任务未保留" })[log.historicalBilling.operation]}`,
            `参考图：${log.historicalBilling.referenceCount ?? "未知"}；保留结果图：${log.historicalBilling.imageCount ?? "未知"}`,
            `尺寸：${log.historicalBilling.size ?? "未知"}；质量：${log.historicalBilling.quality ?? "未知"}`,
            ...(log.historicalBilling.source ? [
                `来源：${log.historicalBilling.source.name}，第 ${log.historicalBilling.source.row} 行`,
                `来源 SHA256：${log.historicalBilling.source.sha256}`,
                `结束时间偏差：${log.historicalBilling.timeDifferenceSeconds} 秒`,
                "关联规则：同模型、结束时间相差不超过 3 秒、耗时相差不超过 5 秒，双向唯一。",
            ] : ["来源：暂未找到唯一对应的供应商账单；金额留空。"]),
        ] : [`费用：${log.billedAmount != null && Number(log.billedAmount) > 0 ? `¥${Number(log.billedAmount).toFixed(2)}` : "成本待结算"}`]),
        ...(log.errorMessage ? [`错误：[${log.errorCategory || "unknown"}] ${log.errorMessage}`] : []),
    ].join("\n");
}
