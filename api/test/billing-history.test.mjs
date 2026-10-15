import assert from "node:assert/strict";
import { after, mock, test } from "node:test";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import Fastify from "fastify";
import { parseBillingHistory, queryBillingHistory } from "../src/billing-history.ts";

const source = { name: "test-only.csv", sha256: "a".repeat(64), rowCount: 3, firstDataRow: 2 };
const log = {
  id: "00000000-0000-4000-8000-000000000001", userId: null, username: null, userDisplayName: null,
  type: "image", taskId: null, textRequestId: null, modelId: null, modelNameSnapshot: "test", modelDisplayNameSnapshot: "Test",
  channelId: null, channelNameSnapshot: "Test", upstreamModel: "test", status: "succeeded", httpStatus: 200,
  errorCategory: null, errorMessage: null, billedAmount: "0.000000", startedAt: "2026-09-01T01:00:00.000Z",
  finishedAt: "2026-09-01T01:00:01.000Z", durationMs: 1000,
  historicalBilling: { status: "candidate", amount: "0.000001", currency: "USD", source: { ...source, row: 2 }, actualConfirmedAmount: null,
    operation: "generation", referenceCount: 0, imageCount: 1, size: null, quality: null, timeDifferenceSeconds: 0.1 },
};
const unknown = structuredClone(log);
unknown.id = "00000000-0000-4000-8000-000000000002";
unknown.status = "failed";
Object.assign(unknown.historicalBilling, { status: "unknown", amount: null, currency: null, source: null });
const zero = structuredClone(log);
zero.id = "00000000-0000-4000-8000-000000000003";
Object.assign(zero.historicalBilling, { amount: "0", currency: "CNY", source: { ...source, row: 4 } });
const fixture = { version: 1, importId: "test-only", importedAt: log.startedAt, snapshotAt: log.startedAt, matchingMethod: "test-only", sources: [source], logs: [log, unknown, zero] };
const query = { limit: 20, offset: 0 };

test("zero and unknown stay separate, currencies stay separate, original amounts stay unchanged", () => {
  const data = parseBillingHistory(JSON.stringify(fixture));
  const result = queryBillingHistory(data, query);
  assert.equal(result.total, 3);
  assert.equal(result.history.candidateCount, 2);
  assert.equal(result.history.unknownCount, 1);
  assert.deepEqual(result.history.candidateTotals, { USD: "0.000001", CNY: "0.000000" });
  assert.equal(result.logs[0].billedAmount, "0.000000");
  assert.equal(result.logs[0].historicalBilling.actualConfirmedAmount, null);
  assert.equal(queryBillingHistory(data, { ...query, reconciliation: "unknown" }).total, 1);
  assert.equal(queryBillingHistory(data, { ...query, status: "failed" }).total, 1);
  assert.equal(queryBillingHistory(data, { ...query, from: "2026-09-01T09:00:01+08:00" }).total, 0);
  assert.equal(queryBillingHistory(data, { ...query, to: log.startedAt }).total, 0);
  assert.equal(queryBillingHistory(data, { ...query, limit: 1, offset: 1 }).logs[0].id, unknown.id);
  assert.equal(queryBillingHistory(undefined, query).history, null);
});

test("invalid or duplicate provenance cannot be imported as an assigned debit", () => {
  for (const change of [
    (f) => f.logs.push(structuredClone(log)),
    (f) => { f.logs[2].historicalBilling.source.row = 2; },
    (f) => { f.logs[0].historicalBilling.source.row = 5; },
    (f) => { f.logs[0].historicalBilling.source.sha256 = "b".repeat(64); },
    (f) => { f.logs[0].historicalBilling.amount = "-1"; },
    (f) => { f.logs[0].historicalBilling.currency = "BTC"; },
    (f) => { f.logs[1].historicalBilling.amount = "0"; },
    (f) => { f.logs[0].historicalBilling.actualConfirmedAmount = "1"; },
  ]) {
    const f = structuredClone(fixture); change(f);
    assert.throws(() => parseBillingHistory(JSON.stringify(f)));
  }
});

mock.module("../src/auth/session.ts", { namedExports: { authenticate: async (req, reply, options) => {
  assert.equal(options.admin, true);
  if (!req.headers["x-test-role"]) { reply.code(401).send({ error: "unauthorized" }); return null; }
  if (req.headers["x-test-role"] !== "admin") { reply.code(403).send({ error: "forbidden" }); return null; }
  return { role: "admin" };
} } });
mock.module("../src/db/client.ts", { namedExports: { db: new Proxy({}, { get() { throw new Error("History must not access or mutate business DB"); } }) } });
const { adminRequestLogRoutes } = await import("../src/routes/admin-request-logs.ts");
const app = Fastify();
app.register(adminRequestLogRoutes, { prefix: "/api/admin/request-logs" });
const dir = mkdtempSync(join(tmpdir(), "canvas-billing-test-"));
after(async () => { await app.close(); rmSync(dir, { recursive: true }); delete process.env.CANVAS_BILLING_HISTORY_PATH; delete process.env.CANVAS_BILLING_HISTORY_SHA256; });

test("history is admin-only, read-only and fails closed on a damaged import", async () => {
  const url = "/api/admin/request-logs/history";
  assert.equal((await app.inject({ url })).statusCode, 401);
  assert.equal((await app.inject({ url, headers: { "x-test-role": "user" } })).statusCode, 403);
  const headers = { "x-test-role": "admin" };
  assert.equal((await app.inject({ url, method: "DELETE", headers })).statusCode, 404);
  process.env.CANVAS_BILLING_HISTORY_PATH = join(dir, "history.json");
  writeFileSync(process.env.CANVAS_BILLING_HISTORY_PATH, JSON.stringify(fixture));
  process.env.CANVAS_BILLING_HISTORY_SHA256 = "bad";
  const damaged = await app.inject({ url, headers });
  assert.equal(damaged.statusCode, 503);
  assert.doesNotMatch(damaged.body, /test-only.csv|00000000|history.json/);
  process.env.CANVAS_BILLING_HISTORY_SHA256 = createHash("sha256").update(JSON.stringify(fixture)).digest("hex");
  const good = await app.inject({ url, headers });
  assert.equal(good.statusCode, 200);
  assert.equal(good.headers["cache-control"], "no-store");
  assert.equal(good.json().total, 3);
  const filtered = await app.inject({ url: url + "?reconciliation=unknown", headers });
  assert.equal(filtered.json().total, 1);
});
