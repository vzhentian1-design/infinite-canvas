import assert from "node:assert/strict";
import { test, mock, afterEach } from "node:test";
import { parseNewApiEvidence, fetchNewApiEvidence, fetchNewApiEvidenceBatch } from "../src/newapi-evidence.ts";

afterEach(() => mock.restoreAll());
test("one bounded log GET batches request identities without mixing settlements", async () => {
  const called=mock.method(globalThis,"fetch",async(url,init)=>{
    assert.deepEqual(url.searchParams.getAll("request_id"),["a","b"]);
    assert.equal(init.headers.Authorization,"Bearer synthetic-only");
    return new Response(JSON.stringify({success:true,data:[{request_id:"b",type:2,quota:20},{request_id:"a",type:2,quota:10},{request_id:"foreign",type:2,quota:900}]}));
  });
  const result=await fetchNewApiEvidenceBatch("https://gateway.example/v1","synthetic-only",["a","b"]);
  assert.equal(result.a.quota,10);assert.equal(result.b.quota,20);assert.equal(called.mock.callCount(),1);
  await assert.rejects(fetchNewApiEvidenceBatch("https://gateway.example/v1","synthetic-only",Array(26).fill("too-many")));
  assert.equal(called.mock.callCount(),1);
});
test("unknown primary plus successful Packy keeps separate currencies and receipts", () => {
  const rows = [
    { request_id: "task-2", type: 2, quota: 14813, channel: 3, upstream_request_id: "packy-2", other: JSON.stringify({ image_attempt: 2, image_supplier: "canvas-packy-flare", upstream_model_name: "gpt-image-2.5-flare", supplier_estimate: {amount:null,currency:"USD",min:"0.029400",max:"3.557850",source:"https://www.packyapi.com/api/pricing"}, supplier_charge: {status:"verified",amount:"0.029626",currency:"USD",request_id:"packy-2",model:"gpt-image-2.5-flare",source:"https://www.packyapi.com/api/log/token",snapshot_sha256:"a".repeat(64)} }) },
    { request_id: "task-2", type: 5, quota: 0, channel: 2, upstream_request_id: "qidong-1", other: JSON.stringify({ image_attempt: 1, status_code:503,image_supplier:"canvas-qidong-flare",upstream_model_name:"gpt-image-2.5-flare",supplier_estimate:{amount:"0.030000",currency:"CNY",source:"https://api.qidong.autos/api/pricing"} }) },
  ];
  const result = parseNewApiEvidence("task-2", rows);
  assert.equal(result.status,"settled");
  assert.equal(result.quota,14813);
  assert.equal(result.supplierCurrency,"USD");
  assert.deepEqual(result.attempts.map(a=>[a.attempt,a.status,a.quota,a.supplierRequestId]),[[1,"unknown",0,"qidong-1"],[2,"succeeded",14813,"packy-2"]]);
  assert.equal(result.attempts[0].supplierAmount,null);
  assert.equal(result.attempts[0].estimate.currency,"CNY");
  assert.equal(result.attempts[1].supplierAmount,"0.029626");
  assert.equal(result.attempts[1].estimate.amount,null);
  const wrongSource = structuredClone(rows);
  const other = JSON.parse(wrongSource[0].other);other.supplier_charge.source="https://api.qidong.autos/api/log/token";wrongSource[0].other=JSON.stringify(other);
  assert.equal(parseNewApiEvidence("task-2",wrongSource).attempts[1].supplierAmount,null);
  assert.deepEqual(parseNewApiEvidence("task-2",rows).attempts,result.attempts);
});
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
