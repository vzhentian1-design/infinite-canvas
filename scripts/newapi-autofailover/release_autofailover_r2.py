"""Release approved tested images/config only; preserve data and recoverable containers."""
import copy,datetime,http.client,http.cookiejar,json,os,pathlib,socket,sqlite3,subprocess,time,urllib.request
os.umask(0o077);root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016');rel=root/'release-r2';rel.mkdir(mode=0o700,exist_ok=True)
prior=pathlib.Path('/opt/canvas-newapi-integration-20261016')
names=['new-api-personal','canvas-migrated-api','canvas-migrated-app']
images={'new-api-personal':'new-api:canvas-autofailover-protocolfix','canvas-migrated-api':'infinite-canvas-api:autofailover-candidate-20261016','canvas-migrated-app':'infinite-canvas:autofailover-candidate-20261016'}
expected={'new-api-personal':'sha256:adbd3f91f50b4e27d64aeac9b5edacc1fb429d71e2148f8eea73f7a99665bd19','canvas-migrated-api':'sha256:b0ad358fb014f5a055f9492484d5051366bf0ca1405ade352df6285f3b812283','canvas-migrated-app':'sha256:8823808ae9ec6e1c6d37f5d9363a4e9fdfcc9e53c313a293cb7ae85d37d719db'}
flare='364f4be2-b4b0-477a-ae7e-069fee4998be';sun='689e1b16-f2fd-4315-b801-5d183cd7c952';gatewayChannel='72215abc-7bf1-4ea9-8890-eaae8fead324'
def run(a,data=None):
 p=subprocess.run(a,input=data,capture_output=True)
 if p.returncode:
  (rel/'last-process-error-private.txt').write_bytes(p.stderr)
  raise RuntimeError(a[0]+' failed; protected diagnostic retained')
 return p.stdout
def inspect(n):return json.loads(run(['docker','inspect',n]))[0]
def node(js):return json.loads(run(['docker','exec','-i','canvas-migrated-api','node','--input-type=module'],js.encode()))
class Engine(http.client.HTTPConnection):
 def connect(self):self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.connect('/var/run/docker.sock')
def engine(path,payload):
 c=Engine('localhost');c.request('POST',path,json.dumps(payload),{'Content-Type':'application/json'});r=c.getresponse();body=r.read();c.close()
 if r.status>=300:raise RuntimeError('Docker operation rejected '+str(r.status))
 return json.loads(body) if body else None
def wait(url):
 for _ in range(60):
  try:
   with urllib.request.urlopen(url,timeout=2) as r:
    if r.status==200:return
  except Exception:time.sleep(.5)
 raise RuntimeError('Health failed '+url)
def wait_api():
 for _ in range(60):
  check=subprocess.run(['docker','exec','canvas-migrated-api','node','-e',"fetch('http://127.0.0.1:3001/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"],capture_output=True)
  if check.returncode==0:return
  time.sleep(.5)
 raise RuntimeError('Internal API health failed')
class Native:
 def __init__(self):self.auth=None;self.uid=None;self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def api(self,path,data=None,method=None):
  h={'Content-Type':'application/json','Origin':'https://newapi.dongyuanhub.com'}
  if self.auth:h.update(Authorization='Bearer '+self.auth,**{'New-Api-User':str(self.uid)})
  with self.opener.open(urllib.request.Request('http://127.0.0.1:3044'+path,data=json.dumps(data).encode() if data is not None else None,headers=h,method=method),timeout=30) as r:p=json.load(r)
  if not p.get('success'):
   (rel/'native-error-private.json').write_text(json.dumps(p));raise RuntimeError('Native API rejected '+path)
  return p.get('data')
 def login(self,file):
  v=self.api('/api/user/login',json.loads(file.read_text()));self.auth=v['access_token'];self.uid=v['user']['id']
 def logout(self):
  self.api('/api/user/auth/logout',{},'POST');self.auth=None;self.uid=None
def sqlite_rows(query,args=()):
 c=sqlite3.connect('file:/opt/new-api/data/new-api.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
 try:return [dict(x) for x in c.execute(query,args)]
 finally:c.close()
def config_node(js):
 api=old['canvas-migrated-api'];net=next(iter(api['NetworkSettings']['Networks']))
 return json.loads(run(['docker','run','--rm','-i','--name','canvas-af-config-run','--network',net,'--env-file',str(rel/'canvas.env'),'--volumes-from','canvas-migrated-api-pre-autofailover-20261016-r2','--entrypoint','node',images['canvas-migrated-api'],'--input-type=module'],js.encode()))
def clone(name):
 original=old[name];cfg=copy.deepcopy(original['Config']);cfg['Hostname']='';cfg['Image']=images[name];cfg['HostConfig']=copy.deepcopy(original['HostConfig']);cfg['NetworkingConfig']={'EndpointsConfig':{n:{'Aliases':v.get('Aliases') or []} for n,v in original['NetworkSettings']['Networks'].items()}}
 cfg['Labels'].pop('com.docker.compose.config-hash',None);cfg['Labels']['com.docker.compose.image']=expected[name]
 override=root/('compose.newapi-autofailover.json' if name=='new-api-personal' else 'compose.canvas-autofailover.json')
 cfg['Labels']['com.docker.compose.project.config_files']+=','+str(override)
 if name=='new-api-personal':
  cfg['Env']=[v for v in cfg['Env'] if not v.startswith(('CANVAS_IMAGE_','CHANNEL_TEST_ENABLED='))]+['CANVAS_IMAGE_ROUTING_ENABLED=true','CANVAS_IMAGE_AMBIGUOUS_FAILOVER_ENABLED=true','CANVAS_IMAGE_PRIMARY_TIMEOUT_SECONDS=180','CANVAS_IMAGE_BACKUP_TIMEOUT_SECONDS=240','CANVAS_IMAGE_FLARE_COOLDOWN_SECONDS=300','CANVAS_IMAGE_SUNBURST_COOLDOWN_SECONDS=300','CHANNEL_TEST_ENABLED=false']
 run(['docker','stop',name]);run(['docker','rename',name,name+'-pre-autofailover-20261016-r2']);replaced.append(name);engine('/containers/create?name='+name,cfg)
 if name!='canvas-migrated-api':engine('/containers/'+name+'/start',{})
def channel_patch(row):
 return {k:row[k] for k in ['id','name','key','base_url','type','models','group','priority','weight','model_mapping','auto_ban','setting','settings','remark'] if k in row}
def token_payload(r):
 return {k:(bool(r[k]) if k in ['unlimited_quota','model_limits_enabled','cross_group_retry'] else r[k]) for k in ['id','name','expired_time','remain_quota','unlimited_quota','model_limits_enabled','model_limits','allow_ips','group','cross_group_retry']}
def configure_native():
 n=Native();n.login(pathlib.Path('/opt/new-api/secrets/admin.json'));options={x['key']:x['value'] for x in n.api('/api/option/')}
 assert options['RetryTimes']=='0'
 for key,entries in priceEntries.items():
  v=json.loads(options.get(key) or '{}');v.update(entries)
  if key=='ModelPrice':v.pop('canvas-packy-flare',None);v.pop('canvas-packy-sunburst',None)
  n.api('/api/option/',{'key':key,'value':json.dumps(v)},'PUT')
 keys={'qidong':(prior/'secrets/qidong-image.key').read_text().strip(),'packy':secretPacky}
 for cid,supplier,variant,priority in [(2,'qidong','flare',100),(3,'packy','flare',10),(None,'qidong','sunburst',100),(None,'packy','sunburst',10)]:
  alias='canvas-image' if variant=='flare' else 'canvas-image-sunburst';name=f'canvas-{supplier}-{variant}'
  rec={'name':name,'key':keys[supplier],'base_url':'https://api.qidong.autos' if supplier=='qidong' else 'https://cf.api.fan','type':1,'models':alias,'group':'canvas-image','priority':priority,'weight':100,'model_mapping':json.dumps({alias:'gpt-image-2.5-'+variant}),'auto_ban':0,'setting':'{}','settings':'{}','remark':'Canvas same-model primary/backup; no scheduled paid probes'}
  if cid:rec['id']=cid;n.api('/api/channel/',rec,'PUT')
  else:
   existing=sqlite_rows('select id from channels where name=?',(name,))
   if existing:
    cid=existing[0]['id'];rec['id']=cid;n.api('/api/channel/',rec,'PUT')
   else:
    n.api('/api/channel/',{'mode':'single','channel':{**rec,'status':2}},'POST');cid=sqlite_rows('select id from channels where name=?',(name,))[0]['id'];createdChannels.append(cid)
  n.api('/api/channel/'+str(cid)+'/status',{'status':1},'POST')
 n.logout();n.login(prior/'secrets/canvas-project-user.json');token=sqlite_rows('select * from tokens where id=5')[0];token['model_limits']='canvas-image,canvas-image-sunburst';n.api('/api/token/',token_payload(token),'PUT');n.logout()
def rollback():
 # Restore only configuration, never overwrite business databases or quota use.
 if 'canvas-migrated-api' in replaced:
  try:run(['docker','stop','canvas-migrated-api'])
  except Exception:pass
  config_node("import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';const b="+json.dumps(canvasBefore,ensure_ascii=False)+";await s.begin(async t=>{await t`update model_channels set enabled=false where model_id in (select id from models where capability='image')`;for(const r of b.models){await t`update models set name=${r.name},display_name=${r.display_name},status=${r.status},sort_order=${r.sort_order},description=${r.description},config=${JSON.stringify(r.config)}::jsonb where id=${r.id}`;}for(const r of b.bindings){await t`update model_channels set enabled=${r.enabled},upstream_model=${r.upstream_model},priority=${r.priority},weight=${r.weight} where id=${r.id}`;}});console.log(JSON.stringify({restored:true}));await closeDatabase();")
 if 'new-api-personal' in replaced:
  n=Native();n.login(pathlib.Path('/opt/new-api/secrets/admin.json'))
  for r in gatewayBefore['channels']:n.api('/api/channel/',channel_patch(r),'PUT');n.api('/api/channel/'+str(r['id'])+'/status',{'status':r['status']},'POST')
  for cid in createdChannels:n.api('/api/channel/'+str(cid)+'/status',{'status':2},'POST')
  current={x['key']:x['value'] for x in n.api('/api/option/')}
  for key,entries in priceEntries.items():
   v=json.loads(current.get(key) or '{}');original=json.loads(gatewayBefore['options'].get(key) or '{}')
   for k in entries:
    if k in original:v[k]=original[k]
    else:v.pop(k,None)
   n.api('/api/option/',{'key':key,'value':json.dumps(v)},'PUT')
  n.logout();n.login(prior/'secrets/canvas-project-user.json');r=sqlite_rows('select * from tokens where id=5')[0];r['model_limits']=gatewayBefore['token']['model_limits'];n.api('/api/token/',token_payload(r),'PUT');n.logout()
 for name in reversed(replaced):
  run(['docker','stop',name]);run(['docker','rename',name,name+'-failed-autofailover-20261016-r2']);run(['docker','rename',name+'-pre-autofailover-20261016-r2',name]);run(['docker','start',name])
 run(['docker','exec','canvas-migrated-app','nginx','-s','reload'])
 (rel/'rolled-back.json').write_text(json.dumps({'at':time.time(),'businessDatabaseRestored':False,'restored':replaced}))
assert not(rel/'started.json').exists(),'Release intent exists; inspect receipt, never replay blindly'
one=json.loads((root/'paid/one-result.json').read_text());fixed=json.loads((root/'paid/protocol-fix-once/two-result.json').read_text());free=json.loads((root/'protocol-fix-free/free-gateway.json').read_text());assert one['status']==fixed['status']=='succeeded' and free['passed']==24
for name in names:
 assert json.loads(run(['docker','image','inspect',images[name]]))[0]['Id']==expected[name]
 assert subprocess.run(['docker','inspect',name+'-pre-autofailover-20261016-r2'],capture_output=True).returncode!=0
old={n:inspect(n) for n in names};(rel/'before-containers-private.json').write_text(json.dumps(old))
canvasBefore=node("import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';console.log(JSON.stringify({counts:(await s`select (select count(*)::int from request_logs) logs,(select count(*)::int from generation_tasks) tasks,(select count(*)::int from generated_images) images,(select count(*)::int from generation_tasks where status in ('queued','running')) inflight`)[0],models:await s`select * from models where capability='image' and deleted_at is null`,bindings:await s`select mc.* from model_channels mc join models m on m.id=mc.model_id where m.capability='image' and m.deleted_at is null`}));await closeDatabase();")
assert canvasBefore['counts']['inflight']==0
assert any(r['id']==flare for r in canvasBefore['models']) and any(r['id']==sun for r in canvasBefore['models'])
(rel/'canvas-config-private.json').write_text(json.dumps(canvasBefore,ensure_ascii=False));(rel/'canvas-before.dump').write_bytes(run(['docker','exec','canvas-migrated-postgres','sh','-c','pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc']))
c=sqlite3.connect('file:/opt/new-api/data/new-api.db?mode=ro',uri=True);b=sqlite3.connect(str(rel/'newapi-before.db'));c.backup(b);b.close();c.close()
gatewayBefore={'channels':sqlite_rows('select * from channels where '+chr(34)+'group'+chr(34)+'='+chr(39)+'canvas-image'+chr(39)),'options':{r['key']:r['value'] for r in sqlite_rows('select * from options')},'token':sqlite_rows('select * from tokens where id=5')[0]};(rel/'native-config-private.json').write_text(json.dumps(gatewayBefore))
secretPacky=node("import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';import{decryptSecret}from'/app/dist/crypto.js';const[r]=await s`select encrypted_api_key from channels where id='0dddb84e-79d7-4256-8851-b165d4acaa4f'`;console.log(JSON.stringify(decryptSecret(r.encrypted_api_key)));await closeDatabase();")
assert all('\n' not in e for e in old['canvas-migrated-api']['Config']['Env']);(rel/'canvas.env').write_text('\n'.join(old['canvas-migrated-api']['Config']['Env'])+'\n')
priceEntries={'ModelPrice':{'canvas-image':.03,'canvas-image-sunburst':.03,'canvas-qidong-flare':.03,'canvas-qidong-sunburst':.03},'ModelRatio':{'canvas-packy-flare':12.5,'canvas-packy-sunburst':12.5},'CompletionRatio':{'canvas-packy-flare':6,'canvas-packy-sunburst':6},'ImageRatio':{'canvas-packy-flare':1.6,'canvas-packy-sunburst':1.6}}
net=next(iter(old['canvas-migrated-api']['NetworkSettings']['Networks']))
(root/'compose.canvas-autofailover.json').write_text(json.dumps({'services':{'api':{'image':images['canvas-migrated-api']},'app':{'image':images['canvas-migrated-app']}}},indent=2))
(root/'compose.newapi-autofailover.json').write_text(json.dumps({'services':{'new-api':{'image':images['new-api-personal'],'environment':{'CANVAS_IMAGE_ROUTING_ENABLED':'true','CANVAS_IMAGE_AMBIGUOUS_FAILOVER_ENABLED':'true','CANVAS_IMAGE_PRIMARY_TIMEOUT_SECONDS':'180','CANVAS_IMAGE_BACKUP_TIMEOUT_SECONDS':'240','CANVAS_IMAGE_FLARE_COOLDOWN_SECONDS':'300','CANVAS_IMAGE_SUNBURST_COOLDOWN_SECONDS':'300','CHANNEL_TEST_ENABLED':'false'},'networks':['default','canvas']}},'networks':{'canvas':{'external':True,'name':net}}},indent=2))
createdChannels=[];replaced=[];(rel/'started.json').write_text(json.dumps({'at':time.time(),'approvedTimeouts':[180,240],'acceptedTasks':[one['taskId'],fixed['taskId']],'paidCallsTotal':3}));print(json.dumps({'backupsReady':True,'releaseStarted':True}),flush=True)
try:
 clone('canvas-migrated-api') # Hold worker/submission endpoint while changing gateway/config.
 clone('new-api-personal');wait('http://127.0.0.1:3044/api/status');configure_native()
 configured=config_node("""import{sqlClient as s,db,closeDatabase}from'/app/dist/db/client.js';import*as schema from'/app/dist/db/schema.js';const ids=['FLARE','SUN'];await s.begin(async tx=>{await tx`update models set status='draft' where capability='image' and deleted_at is null`;for(const[id,name,label,order]of[[ids[0],'canvas-image','GPT Image 2.5 Flare',-100],[ids[1],'canvas-image-sunburst','GPT Image 2.5 Sunburst',-90]]){await tx`update models set name=${name},display_name=${label},status='published',sort_order=${order},description='生成图片或添加参考图改图。3:4比例，标准质量。' where id=${id}`;await tx`update model_channels set enabled=false where model_id=${id}`;await tx`insert into model_channels (model_id,channel_id,upstream_model,priority,enabled) values (${id},'GATEWAY',${name},100,true) on conflict (model_id,channel_id,upstream_model) do update set enabled=true,priority=100`;}});console.log(JSON.stringify({models:await s`select id,name,display_name,sort_order from models where capability='image' and status='published' and deleted_at is null`,bindings:await s`select model_id,channel_id,upstream_model from model_channels where enabled and model_id in (${ids[0]},${ids[1]})`}));await closeDatabase();""".replace('FLARE',flare).replace('SUN',sun).replace('GATEWAY',gatewayChannel))
 assert len(configured['models'])==2 and len(configured['bindings'])==2 and all(x['channel_id']==gatewayChannel for x in configured['bindings'])
 engine('/containers/canvas-migrated-api/start',{});wait_api();clone('canvas-migrated-app');wait('https://canvas.dongyuanhub.com/')
 after=node("import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';import{loadBillingHistory,queryBillingHistory}from'/app/dist/billing-history.js';const h=queryBillingHistory(loadBillingHistory(),{limit:1,offset:0});console.log(JSON.stringify({counts:(await s`select (select count(*)::int from request_logs) logs,(select count(*)::int from generation_tasks) tasks,(select count(*)::int from generated_images) images,(select count(*)::int from generation_tasks where status in ('queued','running')) inflight`)[0],history:{total:h.total,candidates:h.history.candidateCount,unknown:h.history.unknownCount}}));await closeDatabase();")
 assert after['counts']==canvasBefore['counts'] and after['history']=={'total':400,'candidates':272,'unknown':128}
 channels=sqlite_rows('select id,name,status,models,"group",priority,model_mapping from channels where "group"=?',('canvas-image',));assert len(channels)==4 and all(r['status']==1 for r in channels)
 token=sqlite_rows('select id,remain_quota,unlimited_quota,model_limits from tokens where id=5')[0];assert token['remain_quota']==gatewayBefore['token']['remain_quota'] and not token['unlimited_quota']
 protected=[]
 for x in json.loads((root/'paid/before-private.json').read_text()):
  name=x['Name'].lstrip('/')
  if name in names:continue
  now=inspect(name);assert all(x[k]==now[k] for k in ['Id','Config','HostConfig']) and sorted(x['Mounts'],key=lambda r:r['Destination'])==sorted(now['Mounts'],key=lambda r:r['Destination']) and x['State']['StartedAt']==now['State']['StartedAt'];protected.append(name)
 result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deployed':True,'images':expected,'configuration':configured,'channels':channels,'token':token,**after,'protectedUnchanged':protected,'rollbackContainers':[n+'-pre-autofailover-20261016-r2' for n in names],'rollbackDatabaseRestore':False,'realSupplierSends':3,'successfulRealImages':2,'confirmedQidongCNY':.03,'PackySupplierDebit':'pending_verification','employeeUi':'pending_browser_readback','cooldownRecoveryEvidence':'24 free native scenarios; no extra paid probe'}
 (rel/'completed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
except Exception:
 try:rollback();print(json.dumps({'rolledBack':True,'businessDatabaseRestored':False}),flush=True)
 except Exception as e:(rel/'rollback-needs-attention.txt').write_text(str(e));print(json.dumps({'rollbackNeedsAttention':True}),flush=True)
 raise
