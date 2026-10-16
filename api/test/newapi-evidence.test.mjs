import assert from "node:assert/strict";
import { test, mock, afterEach } from "node:test";
import { parseNewApiEvidence, fetchNewApiEvidence } from "../src/newapi-evidence.ts";

afterEach(() => mock.restoreAll());
test("gateway settlements use exact request identity and do not claim supplier cash", () => {
  const rows = [{ request_id: "other", type: 2, quota: 999 }, { request_id: "gateway-1", type: 5, quota: 0 }, { request_id: "gateway-1", type: 2, quota: 15000, channel: 2, upstream_request_id: "supplier-1", other: JSON.stringify({ upstream_model_name: "gpt-image-2.5-flare" }) }];
  const result = parseNewApiEvidence("gateway-1", rows);
  assert.equal(result.quota, 15000);
  assert.equal(result.providerChannelId, 2);
  assert.equal(result.providerModel, "gpt-image-2.5-flare");
  assert.equal(result.supplierRequestId, "supplier-1");
  assert.equal(result.supplierAmount, null);
  assert.equal(result.supplierSettlementStatus, "pending_verification");
  assert.equal(parseNewApiEvidence("gateway-1", rows).quota, 15000);
});
test("missing, ambiguous and refunded settlements retain uncertainty; zero is distinct", () => {
  assert.equal(parseNewApiEvidence("one", []).status, "pending");
  assert.equal(parseNewApiEvidence("one", [{ request_id: "one", type: 2, quota: 0 }]).quota, 0);
  assert.equal(parseNewApiEvidence("one", [{ request_id: "one", type: 2, quota: 10 }, { request_id: "one", type: 2, quota: 10 }]).status, "unknown");
  assert.equal(parseNewApiEvidence("one", [{ request_id: "one", type: 6, quota: 10 }]).status, "unknown");
});
test("settlement uses only a scoped read-only GET with credentials in the header", async () => {
  const called = mock.method(globalThis, "fetch", async (url, init) => {
    assert.equal(url.pathname, "/api/log/token");
    assert.equal(url.searchParams.get("request_id"), "gateway-1");
    assert.equal(url.toString().includes("synthetic-key"), false);
    assert.equal(init.headers.Authorization, "Bearer synthetic-key");
    return new Response(JSON.stringify({ success: true, data: [{ request_id: "gateway-1", type: 2, quota: 15000 }] }));
  });
  assert.equal((await fetchNewApiEvidence("https://gateway.example/v1", "synthetic-key", "gateway-1")).quota, 15000);
  assert.equal(called.mock.callCount(), 1);
});
