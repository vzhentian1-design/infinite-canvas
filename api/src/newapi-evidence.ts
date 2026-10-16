export type NewApiAttempt = {
  attempt: number;
  status: "succeeded" | "failed" | "unknown";
  httpStatus: number | null;
  errorCode: string | null;
  quota: number | null;
  providerChannelId: number | null;
  providerName: string | null;
  providerModel: string | null;
  supplierRequestId: string | null;
  estimate: { amount: string | null; currency: "CNY" | "USD"; min: string | null; max: string | null; source: string } | null;
  supplierSettlementStatus: "pending_verification" | "verified_account_debit";
  supplierAmount: string | null;
  supplierCurrency: "CNY" | "USD" | null;
  supplierEvidence?: { source: string; requestId: string; snapshotSha256: string };
};

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
  supplierCurrency: "CNY" | "USD" | null;
  supplierEvidence?: { source: string; requestId: string; snapshotSha256: string };
  checkedAt: string;
  attempts?: NewApiAttempt[];
};

export function pendingNewApiEvidence(): NewApiEvidence {
  return { status: "pending", requestId: null, quota: null, quotaPerUnit: 500000, providerChannelId: null, providerName: null, providerModel: null, supplierRequestId: null, supplierSettlementStatus: "pending_verification", supplierAmount: null, supplierCurrency: null, checkedAt: new Date().toISOString() };
}

type GatewayLog = { request_id?: unknown; type?: unknown; quota?: unknown; channel?: unknown; upstream_request_id?: unknown; other?: unknown };
const safeId = (value: unknown, max = 200) => typeof value === "string" && value.length <= max && /^[a-zA-Z0-9_-]+$/.test(value) ? value : null;
const money = (value: unknown) => typeof value === "string" && /^\d{1,8}\.\d{6}$/.test(value) ? value : null;

function parseAttempt(row: GatewayLog, index: number): NewApiAttempt {
  let other: Record<string, unknown> = {};
  try { const value = typeof row.other === "string" ? JSON.parse(row.other) : {}; if (value && typeof value === "object") other = value; } catch { /* Keep missing metadata unknown. */ }
  const model = typeof other.upstream_model_name === "string" && other.upstream_model_name.length <= 160 ? other.upstream_model_name : null;
  const name = typeof other.image_supplier === "string" && other.image_supplier.length <= 120 ? other.image_supplier : null;
  const supplierId = safeId(row.upstream_request_id);
  const charge = other.supplier_charge as Record<string, unknown> | undefined;
  const expectedSource = name?.startsWith("canvas-packy-") ? "https://www.packyapi.com/api/log/token" : "https://api.qidong.autos/api/log/token";
  const expectedCurrency = name?.startsWith("canvas-packy-") ? "USD" : "CNY";
  const verified = charge?.status === "verified" && supplierId && charge.request_id === supplierId && charge.source === expectedSource && charge.currency === expectedCurrency && money(charge.amount) !== null && (charge.model === undefined || charge.model === model) && typeof charge.snapshot_sha256 === "string" && /^[a-f0-9]{64}$/.test(charge.snapshot_sha256);
  const estimate = other.supplier_estimate as Record<string, unknown> | undefined;
  const statusCode = Number.isInteger(other.status_code) ? Number(other.status_code) : null;
  return {
    attempt: Number.isSafeInteger(other.image_attempt) && Number(other.image_attempt) > 0 ? Number(other.image_attempt) : index + 1,
    status: row.type === 2 ? "succeeded" : statusCode !== null && [400, 401, 403, 404, 422].includes(statusCode) ? "failed" : "unknown",
    httpStatus: row.type === 2 ? 200 : statusCode,
    errorCode: typeof other.error_code === "string" ? other.error_code.slice(0, 160) : null,
    quota: Number.isSafeInteger(row.quota) && Number(row.quota) >= 0 ? Number(row.quota) : null,
    providerChannelId: Number.isSafeInteger(row.channel) ? Number(row.channel) : null,
    providerName: name, providerModel: model, supplierRequestId: supplierId,
    estimate: estimate && estimate.source === (expectedCurrency === "USD" ? "https://www.packyapi.com/api/pricing" : "https://api.qidong.autos/api/pricing") && estimate.currency === expectedCurrency ? { amount: money(estimate.amount), currency: expectedCurrency, min: money(estimate.min), max: money(estimate.max), source: estimate.source as string } : null,
    supplierSettlementStatus: verified ? "verified_account_debit" : "pending_verification",
    supplierAmount: verified ? charge.amount as string : null, supplierCurrency: verified ? expectedCurrency : null,
    ...(verified ? { supplierEvidence: { source: charge.source as string, requestId: supplierId, snapshotSha256: charge.snapshot_sha256 as string } } : {}),
  };
}

// Replace a snapshot by identity; never add a poll's totals onto earlier totals.
export function parseNewApiEvidence(requestId: string, rows: unknown, quotaPerUnit = 500000): NewApiEvidence {
  if (!safeId(requestId, 64) || !Array.isArray(rows)) throw new Error("Invalid gateway settlement response");
  const matched = rows.filter((row): row is GatewayLog => Boolean(row) && typeof row === "object" && row.request_id === requestId);
  const consumed = matched.filter((row) => row.type === 2);
  const attempts = matched.filter(row => row.type === 2 || row.type === 5).reverse().map(parseAttempt).sort((a, b) => a.attempt - b.attempt);
  const result: NewApiEvidence = { ...pendingNewApiEvidence(), requestId, quotaPerUnit, attempts };
  // Multiple settlements/refunds need a ledger review, not a guessed net amount.
  if (consumed.length > 1 || matched.some((row) => row.type === 6)) return { ...result, status: "unknown" };
  const row = consumed[0];
  if (!row) return { ...result, status: attempts.length ? "unknown" : "pending" };
  if (!Number.isSafeInteger(row.quota) || Number(row.quota) < 0) return { ...result, status: "unknown" };
  const final = parseAttempt(row, 0);
  return { ...result, status: "settled", quota: Number(row.quota), providerChannelId: final.providerChannelId, providerName: final.providerName, providerModel: final.providerModel, supplierRequestId: final.supplierRequestId, supplierSettlementStatus: final.supplierSettlementStatus, supplierAmount: final.supplierAmount, supplierCurrency: final.supplierCurrency, ...(final.supplierEvidence ? { supplierEvidence: final.supplierEvidence } : {}) };
}

export async function fetchNewApiEvidence(baseUrl: string, apiKey: string, requestId: string) {
  return (await fetchNewApiEvidenceBatch(baseUrl, apiKey, [requestId]))[requestId];
}

export async function fetchNewApiEvidenceBatch(baseUrl: string, apiKey: string, requestIds: string[]) {
  if (!requestIds.length || requestIds.length > 25 || requestIds.some(id => !safeId(id, 64))) throw new Error("Invalid gateway request identities");
  const url = new URL(baseUrl);
  url.pathname = "/api/log/token";
  const query = new URLSearchParams();
  for (const id of requestIds) query.append("request_id", id);
  url.search = query.toString();
  const response = await fetch(url, { headers: { Authorization: `Bearer ${apiKey}` }, redirect: "error", signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw new Error("Gateway settlement unavailable");
  const data = await response.json() as { success?: boolean; data?: unknown };
  if (!data.success) throw new Error("Gateway settlement unavailable");
  return Object.fromEntries(requestIds.map(id => [id, parseNewApiEvidence(id, data.data)]));
}
