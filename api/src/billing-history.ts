import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { z } from "zod";

const nullableText = z.string().nullable();
const sourceSchema = z.object({ name: z.string(), sha256: z.string().regex(/^[a-f0-9]{64}$/), rowCount: z.number().int().positive(), firstDataRow: z.number().int().positive() });
const billingSchema = z.object({
  status: z.enum(["candidate", "unknown"]),
  amount: z.string().regex(/^\d+(\.\d{1,6})?$/).nullable(),
  currency: z.enum(["USD", "CNY"]).nullable(),
  source: sourceSchema.extend({ row: z.number().int().positive() }).nullable(),
  actualConfirmedAmount: z.null(),
  operation: z.enum(["generation", "edit", "image_operation_unknown_task_missing"]),
  referenceCount: z.number().int().nonnegative().nullable(),
  imageCount: z.number().int().nonnegative().nullable(),
  size: nullableText,
  quality: nullableText,
  timeDifferenceSeconds: z.number().nonnegative().nullable(),
});
const logSchema = z.object({
  id: z.string().uuid(), userId: nullableText, username: nullableText, userDisplayName: nullableText,
  type: z.literal("image"), taskId: nullableText, textRequestId: nullableText,
  modelId: nullableText, modelNameSnapshot: nullableText, modelDisplayNameSnapshot: nullableText,
  channelId: nullableText, channelNameSnapshot: nullableText, upstreamModel: nullableText,
  status: z.enum(["running", "succeeded", "failed"]), httpStatus: z.number().nullable(),
  errorCategory: nullableText, errorMessage: nullableText, billedAmount: nullableText,
  startedAt: z.string().datetime(), finishedAt: z.string().datetime().nullable(), durationMs: z.number().nullable(),
  historicalBilling: billingSchema,
});
const historySchema = z.object({
  version: z.literal(1), importId: z.string(), importedAt: z.string().datetime(), snapshotAt: z.string().datetime(),
  matchingMethod: z.string(), sources: z.array(sourceSchema), logs: z.array(logSchema),
}).superRefine((data, ctx) => {
  const ids = new Set<string>();
  const allocations = new Set<string>();
  for (const log of data.logs) {
    const b = log.historicalBilling;
    if (ids.has(log.id)) ctx.addIssue({ code: "custom", message: "Duplicate request ID" });
    ids.add(log.id);
    if (b.status === "candidate") {
      const source = data.sources.find((s) => s.name === b.source?.name && s.sha256 === b.source.sha256);
      const allocation = `${b.source?.sha256}:${b.source?.row}`;
      if (b.amount === null || b.currency === null || !source || !b.source || b.source.row < source.firstDataRow || b.source.row >= source.firstDataRow + source.rowCount || allocations.has(allocation)) {
        ctx.addIssue({ code: "custom", message: "Invalid or duplicate supplier allocation" });
      }
      allocations.add(allocation);
    } else if (b.amount !== null || b.currency !== null || b.source !== null) {
      ctx.addIssue({ code: "custom", message: "Unresolved records cannot have an assigned debit" });
    }
  }
});

export function parseBillingHistory(raw: string) {
  return historySchema.parse(JSON.parse(raw));
}
type History = ReturnType<typeof parseBillingHistory>;
type Query = { from?: string; to?: string; userId?: string; modelId?: string; channelId?: string; type?: string; status?: string; reconciliation?: "candidate" | "unknown"; limit: number; offset: number };

export function attachBillingHistory<T extends { id: string; type: string }>(logs: T[], history: History | undefined) {
  const index = new Map(history?.logs.map((l) => [l.id, l.historicalBilling]));
  return logs.map((log) => ({ ...log, historicalBilling: log.type === "image" ? index.get(log.id) : undefined }));
}

// The source bundle is a server-only, read-only mount. It survives request-log retention.
let cached: History | undefined;
export function loadBillingHistory() {
  const path = process.env.CANVAS_BILLING_HISTORY_PATH;
  if (!path) return undefined;
  if (!cached) {
    const raw = readFileSync(path, "utf8");
    const expected = process.env.CANVAS_BILLING_HISTORY_SHA256;
    if (!expected || createHash("sha256").update(raw).digest("hex") !== expected) throw new Error("Billing history integrity check failed");
    cached = parseBillingHistory(raw);
  }
  return cached;
}

export function queryBillingHistory(history: History | undefined, query: Query) {
  const logs = (history?.logs ?? []).filter((l) =>
    (!query.from || l.startedAt >= new Date(query.from).toISOString()) &&
    (!query.to || l.startedAt < new Date(query.to).toISOString()) &&
    (!query.userId || l.userId === query.userId) && (!query.modelId || l.modelId === query.modelId) &&
    (!query.channelId || l.channelId === query.channelId) && (!query.type || l.type === query.type) &&
    (!query.status || l.status === query.status) && (!query.reconciliation || l.historicalBilling.status === query.reconciliation)
  ).sort((a, b) => b.startedAt.localeCompare(a.startedAt) || a.id.localeCompare(b.id));
  const totalMicros = { USD: 0n, CNY: 0n };
  for (const log of logs) {
    const b = log.historicalBilling;
    if (b.amount !== null && b.currency) {
      const [whole = "0", fraction = ""] = b.amount.split(".");
      totalMicros[b.currency] += BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, "0"));
    }
  }
  const format = (value: bigint) => `${value / 1000000n}.${String(value % 1000000n).padStart(6, "0")}`;
  return {
    logs: logs.slice(query.offset, query.offset + query.limit), total: logs.length,
    history: history ? {
      importId: history.importId, importedAt: history.importedAt, snapshotAt: history.snapshotAt,
      matchingMethod: history.matchingMethod, importedCount: history.logs.length,
      candidateCount: logs.filter((l) => l.historicalBilling.status === "candidate").length,
      unknownCount: logs.filter((l) => l.historicalBilling.status === "unknown").length,
      candidateTotals: { USD: format(totalMicros.USD), CNY: format(totalMicros.CNY) },
    } : null,
  };
}
