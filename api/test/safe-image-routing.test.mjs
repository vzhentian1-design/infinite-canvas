import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { after, afterEach, beforeEach, mock, test } from "node:test";
import { eq } from "drizzle-orm";
import { channels, modelChannels, models } from "../src/db/schema.ts";
import { createTestDatabase } from "./helpers/database.mjs";
import { imageCostEvidence } from "../src/image-cost.ts";

const { client, db } = await createTestDatabase();
mock.module("../src/db/client.ts", { namedExports: { db } });
mock.module("../src/config.ts", { namedExports: { config: {
  CHANNEL_ENCRYPTION_KEY: "safe-image-routing-test-key-long-enough",
  MAX_GENERATED_BYTES: 50 * 1024 * 1024, ALLOW_PRIVATE_IMAGE_HOSTS: false,
} } });
const { runWithFailover, getChannelCandidates, UpstreamError } = await import("../src/channel-scheduler.ts");
const { generateImage } = await import("../src/upstream.ts");
const modelId = randomUUID(), ids = [randomUUID(), randomUUID(), randomUUID()];
beforeEach(async () => {
  await client.exec("truncate models, channels cascade");
  await db.insert(models).values({ id: modelId, name: "logical-image", displayName: "Image", capability: "image", status: "published" });
  await db.insert(channels).values(ids.map((id, i) => ({ id, name: `channel-${i}`, protocol: "openai", baseUrl: "https://invalid.invalid/v1", status: "active", timeoutMs: 60000 })));
  await db.insert(modelChannels).values(ids.map((channelId, i) => ({ modelId, channelId, upstreamModel: i ? "gpt-image-2" : "gpt-image-2-qidong", priority: 30 - i })));
});
afterEach(() => mock.restoreAll());
after(() => client.close());

for (const [category, status, failover] of [["http_503", 503, "always"], ["http_429", 429, "always"], ["http_403", 403, "always"], ["timeout", undefined, "always"], ["network", undefined, "always"], ["invalid_response", undefined, "once"], ["content_policy", 400, "never"]]) {
  test(`image ${category} never sends a second paid request`, async () => {
    const calls = [];
    await assert.rejects(runWithFailover(modelId, async (candidate) => {
      calls.push(candidate.channelId);
      throw new UpstreamError("synthetic failure", category, status, failover);
    }, { safeImage: true }));
    assert.deepEqual(calls, [ids[0]]);
  });
}

test("auth fallback is bounded to two attempts; expired cooldown restores primary priority", async () => {
  const calls = [];
  await assert.rejects(runWithFailover(modelId, async (candidate) => {
    calls.push(candidate.channelId);
    throw new UpstreamError("auth rejected", "http_401", 401, "always");
  }, { safeImage: true }));
  assert.deepEqual(calls, ids.slice(0, 2));
  assert.equal((await getChannelCandidates(modelId))[0].channelId, ids[2]);
  await db.update(channels).set({ cooldownUntil: new Date(Date.now() - 1000) }).where(eq(channels.id, ids[0]));
  const result = await runWithFailover(modelId, async () => "ok", { safeImage: true });
  assert.equal(result.candidate.channelId, ids[0]);
});

test("Canvas sends once to New API, including an explicit 401; mixed bindings fail closed", async () => {
  await db.update(models).set({ config: { routing: "newapi" } }).where(eq(models.id, modelId));
  const calls = [];
  await assert.rejects(runWithFailover(modelId, async (candidate) => calls.push(candidate), { safeImage: true }), /统一生图渠道/);
  assert.equal(calls.length, 0);
  await db.delete(modelChannels).where(eq(modelChannels.channelId, ids[1]));
  await db.delete(modelChannels).where(eq(modelChannels.channelId, ids[2]));
  await assert.rejects(runWithFailover(modelId, async (candidate) => {
    calls.push(candidate.channelId);
    throw new UpstreamError("rejected", "http_401", 401, "always");
  }, { safeImage: true }));
  assert.deepEqual(calls, [ids[0]]);
});

test("estimates follow actual supplier; absent estimates and actual charges remain unknown", async () => {
  await db.update(models).set({ config: { channelEstimates: { [ids[0]]: { amount: "0.03", currency: "CNY" } } } }).where(eq(models.id, modelId));
  const candidates = await getChannelCandidates(modelId);
  assert.equal(candidates[0].estimateSnapshot.amount, "0.03");
  assert.equal(candidates[1].estimateSnapshot, null);
  const cost = imageCostEvidence({ status: "failed", errorCategory: "http_503", estimateSnapshot: null });
  assert.equal(cost.generationOutcome, "unknown");
  assert.equal(cost.supplierActualAmount, null);
  assert.equal(cost.platformEstimate, null);
});

test("generation and multi-reference edit preserve model, size, quality, n=1, and request IDs", async () => {
  const [candidate] = await getChannelCandidates(modelId);
  const calls = [];
  mock.method(globalThis, "fetch", async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({ data: [{ b64_json: "aGVsbG8=" }] }), { headers: { "x-request-id": `synthetic-${calls.length}` } });
  });
  await generateImage(candidate, "test", { size: "768x1024", quality: "low", n: 20 }, []);
  assert.equal(candidate.upstreamRequestId, "synthetic-1");
  const body = JSON.parse(calls[0].init.body);
  assert.deepEqual([body.model, body.size, body.quality, body.n], ["gpt-image-2-qidong", "768x1024", "low", 1]);
  const refs = [1, 2].map((i) => ({ buffer: Buffer.from("test"), filename: `${i}.png`, mimeType: "image/png" }));
  await generateImage(candidate, "edit", { size: "768x1024", quality: "low" }, refs);
  assert.ok(calls[1].url.endsWith("/images/edits"));
  assert.equal(calls[1].init.body.getAll("image").length, 2);
  assert.equal(calls[1].init.body.get("n"), "1");
  assert.equal(candidate.upstreamRequestId, "synthetic-2");
});

test("employee identity is forwarded only to the configured New API gateway", async () => {
  const [candidate] = await getChannelCandidates(modelId);
  Object.assign(candidate, { gateway: true, taskId: "11111111-1111-4111-8111-111111111111", canvasUserId: "22222222-2222-4222-8222-222222222222", canvasUsername: "employee1" });
  const calls = [];
  mock.method(globalThis, "fetch", async (_, init) => {
    calls.push(init.headers);
    return new Response(JSON.stringify({ data: [{ b64_json: "aGVsbG8=" }] }), { headers: { "x-oneapi-request-id": "gateway-1" } });
  });
  await generateImage(candidate, "fixture", { size: "768x1024" }, []);
  assert.equal(calls[0]["X-Canvas-User-Id"], candidate.canvasUserId);
  assert.equal(calls[0]["X-Canvas-Username"], "employee1");
  candidate.gateway = false;
  await generateImage(candidate, "fixture", { size: "768x1024" }, []);
  assert.equal(calls[1]["X-Canvas-User-Id"], undefined);
  assert.equal(calls[1]["X-Canvas-Username"], undefined);
});
