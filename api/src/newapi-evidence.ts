export type NewApiEvidence = {
  status: "pending" | "settled" | "unknown";
  requestId: string | null;
  quota: number | null;
  quotaPerUnit: number;
  providerChannelId: number | null;
  providerName: string | null;
  providerModel: string | null;
  supplierRequestId: string | null;
  supplierSettlementStatus: "pending_verification" | "verified_account_debit";
  supplierAmount: string | null;
  supplierCurrency: "CNY" | null;
  supplierEvidence?: { source: string; requestId: string; snapshotSha256: string };
  checkedAt: string;
};

export function pendingNewApiEvidence(): NewApiEvidence {
  return { status: "pending", requestId: null, quota: null, quotaPerUnit: 500000, providerChannelId: null, providerName: null, providerModel: null, supplierRequestId: null, supplierSettlementStatus: "pending_verification", supplierAmount: null, supplierCurrency: null, checkedAt: new Date().toISOString() };
}

type GatewayLog = { request_id?: unknown; type?: unknown; quota?: unknown; channel?: unknown; upstream_request_id?: unknown; other?: unknown };
const safeId = (value: unknown, max = 200) => typeof value === "string" && value.length <= max && /^[a-zA-Z0-9_-]+$/.test(value) ? value : null;

// Replace a snapshot by identity; never add a poll's totals onto earlier totals.
export function parseNewApiEvidence(requestId: string, rows: unknown, quotaPerUnit = 500000): NewApiEvidence {
  if (!safeId(requestId, 64) || !Array.isArray(rows)) throw new Error("Invalid gateway settlement response");
  const matched = rows.filter((row): row is GatewayLog => Boolean(row) && typeof row === "object" && row.request_id === requestId);
  const consumed = matched.filter((row) => row.type === 2);
  const result: NewApiEvidence = { ...pendingNewApiEvidence(), requestId, quotaPerUnit };
  // Multiple settlements/refunds need a ledger review, not a guessed net amount.
  if (consumed.length > 1 || matched.some((row) => row.type === 6)) return { ...result, status: "unknown" };
  const row = consumed[0];
  if (!row) return result;
  if (!Number.isSafeInteger(row.quota) || Number(row.quota) < 0) return { ...result, status: "unknown" };
  let other: Record<string, unknown> = {};
  try { other = typeof row.other === "string" ? JSON.parse(row.other) : {}; } catch { /* Routing metadata is optional. */ }
  const model = other && typeof other === "object" ? other.upstream_model_name : null;
  const supplierId = safeId(row.upstream_request_id);
  const charge = other?.supplier_charge as Record<string, unknown> | undefined;
  const verified = charge?.status === "verified" && supplierId && charge.request_id === supplierId && charge.source === "https://api.qidong.autos/api/log/token" && charge.currency === "CNY" && typeof charge.amount === "string" && /^\d{1,8}\.\d{6}$/.test(charge.amount) && typeof charge.snapshot_sha256 === "string" && /^[a-f0-9]{64}$/.test(charge.snapshot_sha256);
  return { ...result, status: "settled", quota: Number(row.quota), providerChannelId: Number.isSafeInteger(row.channel) ? Number(row.channel) : null, providerName: typeof other?.image_supplier === "string" && other.image_supplier.length <= 120 ? other.image_supplier : null, providerModel: typeof model === "string" && model.length <= 160 ? model : null, supplierRequestId: supplierId, ...(verified ? { supplierSettlementStatus: "verified_account_debit", supplierAmount: charge.amount as string, supplierCurrency: "CNY", supplierEvidence: { source: charge.source as string, requestId: supplierId, snapshotSha256: charge.snapshot_sha256 as string } } : {}) };
}

export async function fetchNewApiEvidence(baseUrl: string, apiKey: string, requestId: string) {
  const url = new URL(baseUrl);
  url.pathname = "/api/log/token";
  url.search = new URLSearchParams({ request_id: requestId }).toString();
  const response = await fetch(url, { headers: { Authorization: `Bearer ${apiKey}` }, redirect: "error", signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error("Gateway settlement unavailable");
  const data = await response.json() as { success?: boolean; data?: unknown };
  if (!data.success) throw new Error("Gateway settlement unavailable");
  return parseNewApiEvidence(requestId, data.data);
}
