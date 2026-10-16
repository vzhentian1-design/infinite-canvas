"""Bounded read-only provider and deployment discovery. Never invokes inference."""
import concurrent.futures, datetime, hashlib, json, os, pathlib, sqlite3, subprocess, urllib.request, urllib.error
os.umask(0o077)
root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016');root.mkdir(mode=0o700,exist_ok=True)
def run(args,data=None): return subprocess.check_output(args,input=data)
def node(js):return json.loads(run(['docker','exec','-i','canvas-migrated-api','node','--input-type=module'],js.encode()))
keys=node("""import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';import{decryptSecret}from'/app/dist/crypto.js';const rows=await s`select name,encrypted_api_key from channels where deleted_at is null and name in ('Packy','qidong')`;console.log(JSON.stringify(Object.fromEntries(rows.map(r=>[r.name,decryptSecret(r.encrypted_api_key)]))));await closeDatabase();""")
keys['qidong']=pathlib.Path('/opt/canvas-newapi-integration-20261016/secrets/qidong-image.key').read_text().strip()
def fetch(task):
    supplier,url,auth=task
    h={'User-Agent':'Mozilla/5.0','Accept':'application/json'}
    if auth:h['Authorization']='Bearer '+keys[supplier]
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=20) as response:
            body=response.read(8<<20);status=response.status
        payload=json.loads(body)
        data=payload.get('data',[])
        out={'supplier':supplier,'url':url,'http':status,'sha256':hashlib.sha256(body).hexdigest(),'success':payload.get('success'),'message':str(payload.get('message','')).replace(keys[supplier],'[REDACTED]')[:200]}
        if url.endswith('/models'):out['models']=[x for x in data if 'image' in x.get('id','')]
        elif '/pricing' in url:
            out.update(prices=[x for x in data if any(y in x.get('model_name','') for y in ['gpt-image-2.5','gpt-image-2'])],group_ratio=payload.get('group_ratio'),usable_group=payload.get('usable_group'),supported_endpoint=payload.get('supported_endpoint'))
        elif '/log/' in url:
            if isinstance(data,dict):data=data.get('items',[])
            out.update(recordCount=len(data),records=[{k:x.get(k) for k in ['request_id','upstream_request_id','model_name','quota','type','created_at','other']} for x in data[:8]])
        elif '/usage/' in url:out['usage']={k:v for k,v in (data or {}).items() if k not in ['key','token']}
        else:out['data']=payload
        return out
    except urllib.error.HTTPError as e:return {'supplier':supplier,'url':url,'http':e.code}
    except Exception as e:return {'supplier':supplier,'url':url,'error':type(e).__name__}
tasks=[('qidong','https://api.qidong.autos'+p,a) for p,a in [('/v1/models',True),('/api/pricing',False),('/api/log/token',True),('/api/usage/token',True)]]
tasks += [('Packy',b+p,a) for b in ['https://cf.api.fan','https://www.packyapi.com'] for p,a in [('/v1/models',True),('/api/pricing',False),('/api/log/token',True),('/api/usage/token',True)]]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:checks=list(pool.map(fetch,tasks))
runtime=node("""import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';import{loadBillingHistory,queryBillingHistory}from'/app/dist/billing-history.js';const h=queryBillingHistory(loadBillingHistory(),{limit:1,offset:0});console.log(JSON.stringify({counts:(await s`select (select count(*)::int from request_logs) logs,(select count(*)::int from generation_tasks) tasks,(select count(*)::int from generated_images) images,(select count(*)::int from generation_tasks where status in ('queued','running')) inflight`)[0],models:await s`select m.id,m.name,m.display_name,m.status,m.config,m.sort_order,c.name channel,mc.channel_id,mc.upstream_model,mc.priority,mc.enabled from models m left join model_channels mc on mc.model_id=m.id left join channels c on c.id=mc.channel_id where m.capability='image' and m.deleted_at is null`,history:{total:h.total,...h.history}}));await closeDatabase();""")
c=sqlite3.connect('file:/opt/new-api/data/new-api.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
gateway={'channels':[dict(r) for r in c.execute('select id,name,status,base_url,models,"group",priority,model_mapping from channels where "group"=?',('canvas-image',))],'tokens':[dict(r) for r in c.execute('select id,name,status,remain_quota,model_limits,"group" from tokens where user_id=3')],'quota':c.execute('select quota from users where id=3').fetchone()[0]};c.close()
names=['canvas-migrated-api','canvas-migrated-app','new-api-personal','canvas-migrated-postgres','canvas-migrated-minio','sw-new-api-rc39','dongyuan-trial-postgres']
containers=json.loads(run(['docker','inspect',*names]));(root/'before-private.json').write_text(json.dumps(containers))
result={'observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'canvas':runtime,'gateway':gateway,'containers':[{'name':x['Name'],'id':x['Id'],'image':x['Image'],'startedAt':x['State']['StartedAt']} for x in containers],'inferenceCalls':0}
(root/'probe-safe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
