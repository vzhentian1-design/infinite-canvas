import { and, eq, isNotNull, sql } from "drizzle-orm";
import { decryptSecret } from "./crypto.js";
import { db } from "./db/client.js";
import { channels, requestLogs } from "./db/schema.js";
import { fetchNewApiEvidence } from "./newapi-evidence.js";

let syncing = false;
export async function syncNewApiSettlements() {
  if (syncing) return;
  syncing = true;
  try {
    const rows = await db.select({ id: requestLogs.id, requestId: requestLogs.gatewayRequestId, baseUrl: channels.baseUrl, encryptedKey: channels.encryptedApiKey })
      .from(requestLogs).innerJoin(channels, eq(channels.id, requestLogs.channelId))
      .where(and(isNotNull(requestLogs.gatewayRequestId), sql`coalesce(${requestLogs.gatewayEvidence}->>'status', 'pending') = 'pending'`, sql`${requestLogs.startedAt} > now() - interval '7 days'`))
      .orderBy(requestLogs.startedAt).limit(25);
    for (const row of rows) {
      if (!row.requestId || !row.encryptedKey) continue;
      try {
        const evidence = await fetchNewApiEvidence(row.baseUrl, decryptSecret(row.encryptedKey), row.requestId);
        await db.update(requestLogs).set({ gatewayEvidence: evidence, ...(evidence.supplierRequestId ? { upstreamRequestId: evidence.supplierRequestId } : {}) }).where(and(eq(requestLogs.id, row.id), eq(requestLogs.gatewayRequestId, row.requestId)));
      } catch { /* Preserve pending; a failed GET must never cause image generation. */ }
    }
  } finally { syncing = false; }
}

export function startNewApiSettlementSync() {
  const sync = () => void syncNewApiSettlements().catch(() => console.warn("[settlement] 网关结算同步暂不可用"));
  sync();
  const timer = setInterval(sync, 30000);
  timer.unref();
  return timer;
}
