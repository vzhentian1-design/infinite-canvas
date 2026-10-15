// A failed local task does not establish that the supplier did no work or charged zero.
export function isUnknownImageOutcome(category: string | null) {
  return !category || !["http_401", "http_403", "content_policy", "invalid_request", "no_channel", "queue_unavailable", "channel_busy", "reference_too_large", "audit_unavailable"].includes(category);
}

export function imageCostEvidence(log: {
  status: string; errorCategory: string | null;
  estimateSnapshot: { amount: string; currency: string; source: string } | null;
}) {
  return {
    generationOutcome: log.status === "succeeded" ? "succeeded" : log.status === "running" ? "pending" : isUnknownImageOutcome(log.errorCategory) ? "unknown" : "failed",
    platformEstimate: log.estimateSnapshot,
    supplierSettlementStatus: "unknown" as const,
    supplierActualAmount: null,
    supplierActualCurrency: null,
  };
}
