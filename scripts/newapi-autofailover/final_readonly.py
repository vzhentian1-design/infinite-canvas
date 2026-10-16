import datetime,hashlib,json,os,pathlib,sqlite3,subprocess,urllib.request
os.umask(0o077);root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016')
def run(a,data=None):return subprocess.check_output(a,input=data,stderr=subprocess.PIPE)
before=json.loads((root/'before-private.json').read_text());names=[x['Name'].lstrip('/') for x in before];after=json.loads(run(['docker','inspect',*names]))
checks=[]
for old,new in zip(before,after):
    unchanged=all(old[k]==new[k] for k in ['Id','Config','HostConfig']) and sorted(old['Mounts'],key=lambda m:m['Destination'])==sorted(new['Mounts'],key=lambda m:m['Destination']) and old['State']['StartedAt']==new['State']['StartedAt']
    assert unchanged,old['Name']+' changed'
    checks.append({'name':old['Name'],'unchanged':unchanged})
js="""import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';import{loadBillingHistory,queryBillingHistory}from'/app/dist/billing-history.js';const h=queryBillingHistory(loadBillingHistory(),{limit:1,offset:0});console.log(JSON.stringify({counts:(await s`select (select count(*)::int from request_logs) logs,(select count(*)::int from generation_tasks) tasks,(select count(*)::int from generated_images) images,(select count(*)::int from generation_tasks where status in ('queued','running')) inflight`)[0],publishedImageModels:await s`select name,display_name from models where capability='image' and status='published' and deleted_at is null`,history:{total:h.total,candidates:h.history.candidateCount,unknown:h.history.unknownCount}}));await closeDatabase();"""
canvas=json.loads(run(['docker','exec','-i','canvas-migrated-api','node','--input-type=module'],js.encode()))
assert canvas['counts']=={'logs':412,'tasks':261,'images':227,'inflight':0} and canvas['history']=={'total':400,'candidates':272,'unknown':128}
db=sqlite3.connect('file:/opt/new-api/data/new-api.db?mode=ro',uri=True);db.row_factory=sqlite3.Row
channels=[dict(r) for r in db.execute('select id,name,status,base_url,models,"group",priority,model_mapping from channels where "group"=?',('canvas-image',))];db.close()
prior=json.loads((root/'probe-safe.json').read_text())['gateway']['channels'];assert sorted(channels,key=lambda r:r['id'])==sorted(prior,key=lambda r:r['id'])
health={}
for url in ['https://canvas.dongyuanhub.com/','http://127.0.0.1:13001/health','http://127.0.0.1:3044/api/status']:
    with urllib.request.urlopen(url,timeout=15) as response:health[url]=response.status
assert all(v==200 for v in health.values())
fee=json.loads((root/'free-gateway.json').read_text());assert fee['passed']==24
for r in fee['results']:
    for row in r['logs']:
        meta=json.loads(row['other'])
        assert row['quota']==(15000 if row['type']==2 and meta['image_supplier'].startswith('canvas-qidong-') else 14813 if row['type']==2 else 0)
        assert meta['supplier_estimate']['currency']==('CNY' if meta['image_supplier'].startswith('canvas-qidong-') else 'USD')
        assert meta['supplier_estimate']['amount']==('0.030000' if meta['image_supplier'].startswith('canvas-qidong-') else None)
p=root/'database-free';dbs=[]
for engine in ['sqlite','postgres','mysql']:
    body=(p/(engine+'.log')).read_bytes();assert b'PASS' in body;dbs.append({'engine':engine,'PASS':True,'sha256':hashlib.sha256(body).hexdigest()})
body=run(['docker','logs','canvas-af-pg-query-run']);lines=body.decode().splitlines();pg=next(json.loads(x) for x in lines if x.startswith('{"PASS":true'));(p/'canvas-pg-final.log').write_bytes(body)
testnames=['canvas-autofailover-free','canvas-af-postgres','canvas-af-mysql','canvas-af-pg-query-run']
stopped={n:not json.loads(run(['docker','inspect',n]))[0]['State']['Running'] for n in testnames};assert all(stopped.values())
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'productionAndProtectedContainers':checks,'canvas':canvas,'gatewayChannelsUnchanged':True,'health':health,'freeGatewayScenarios':24,'perSupplierPricingAssertions':'PASS','databases':dbs,'canvasPostgres':pg,'testContainersStopped':stopped,'paidInferenceRequests':0,'deployedThisPhase':False}
(root/'final-safe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
