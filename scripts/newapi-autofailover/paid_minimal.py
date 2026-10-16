"""Approved two real sends only. Separate prepare/one/two; durable no-replay guards."""
import copy,datetime,hashlib,http.client,http.cookiejar,http.server,json,os,pathlib,secrets,socket,sqlite3,subprocess,sys,threading,time,urllib.parse,urllib.request
os.umask(0o077)
root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016');out=root/'paid';out.mkdir(mode=0o700,exist_ok=True)
oldroot=pathlib.Path('/opt/canvas-newapi-integration-20261016')
gateway='canvas-af-paid-gateway';canvas='canvas-af-paid-api';database='canvas_af_paid_20261016'
def run(a,data=None):
 p=subprocess.run(a,input=data,capture_output=True)
 if p.returncode:raise RuntimeError(a[0]+' failed; see protected process log')
 return p.stdout
def inspect(n):return json.loads(run(['docker','inspect',n]))[0]
def node(js,name='canvas-migrated-api'):return json.loads(run(['docker','exec','-i',name,'node','--input-type=module'],js.encode()))
class Engine(http.client.HTTPConnection):
 def connect(self):self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.connect('/var/run/docker.sock')
def engine(path,payload):
 c=Engine('localhost');c.request('POST',path,json.dumps(payload),{'Content-Type':'application/json'});r=c.getresponse();b=r.read();c.close()
 if r.status>=300:raise RuntimeError('Docker operation rejected '+str(r.status))
 return json.loads(b) if b else None
def create(name,cfg):
 assert subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0,'Existing fixture, refuse recreate'
 engine('/containers/create?name='+name,cfg);engine('/containers/'+name+'/start',{})
def wait(url):
 for _ in range(60):
  try:
   with urllib.request.urlopen(url,timeout=2) as r:
    if r.status==200:return
  except Exception:time.sleep(.5)
 raise RuntimeError('Fixture health failed')
def fetch(url,key=None):
 headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}
 if key:headers['Authorization']='Bearer '+key
 with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=20) as r:return json.load(r)
def prepare():
 assert not(out/'prepared.json').exists(),'Already prepared'
 before=json.loads(run(['docker','inspect','canvas-migrated-api','canvas-migrated-app','new-api-personal','canvas-migrated-postgres','canvas-migrated-minio','sw-new-api-rc39','dongyuan-trial-postgres']))
 (out/'before-private.json').write_text(json.dumps(before))
 counts=node("import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';console.log(JSON.stringify((await s`select (select count(*)::int from request_logs) logs,(select count(*)::int from generation_tasks) tasks,(select count(*)::int from generated_images) images,(select count(*)::int from generation_tasks where status in ('queued','running')) inflight`)[0]));await closeDatabase();")
 assert counts['inflight']==0
 keys=node("import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';import{decryptSecret}from'/app/dist/crypto.js';const[r]=await s`select encrypted_api_key from channels where id='0dddb84e-79d7-4256-8851-b165d4acaa4f'`;console.log(JSON.stringify({Packy:decryptSecret(r.encrypted_api_key)}));await closeDatabase();")
 keys['qidong']=(oldroot/'secrets/qidong-image.key').read_text().strip()
 qp=fetch('https://api.qidong.autos/api/pricing');pp=fetch('https://www.packyapi.com/api/pricing');balance=fetch('https://www.packyapi.com/api/usage/token',keys['Packy'])
 (out/'provider-check-private.json').write_text(json.dumps({'qidong':qp,'Packy':pp,'balance':balance}))
 q=next(x for x in qp['data'] if x['model_name']=='gpt-image-2.5-sunburst');p=next(x for x in pp['data'] if x['model_name']=='gpt-image-2.5-flare')
 assert float(q['model_price'])==.03 and float(p['model_ratio'])==2.5 and float(p['completion_ratio'])==6 and float(p['image_ratio'])==1.6
 assert float(pp['group_ratio']['image'])==5
 assert balance.get('message')=='ok' and balance['data']['total_available']>0,'No available balance; do not recharge'
 api=inspect('canvas-migrated-api');net=next(iter(api['NetworkSettings']['Networks']));host=json.loads(run(['docker','network','inspect',net]))[0]['IPAM']['Config'][0]['Gateway']
 (out/'host.txt').write_text(host)
 data=out/'data';data.mkdir(exist_ok=True)
 src=sqlite3.connect('file:/opt/new-api/data/new-api.db?mode=ro',uri=True);db=sqlite3.connect(str(data/'new-api.db'));src.backup(db);src.close();db.row_factory=sqlite3.Row
 template=dict(db.execute('select * from channels where id=2').fetchone())
 db.execute("update channels set key='disabled-test-only',status=2,base_url='http://127.0.0.1:1'");db.execute('update abilities set enabled=0');db.execute('delete from logs');db.execute("update tokens set status=2,key='disabled-'||id")
 for cid,supplier,variant,priority,enabled in [(2,'qidong','flare',100,1),(3,'packy','flare',10,1),(4,'qidong','sunburst',100,1),(5,'packy','sunburst',10,0)]:
  alias='canvas-image' if variant=='flare' else 'canvas-image-sunburst'
  url=f'http://{host}:13059' if cid==2 else 'https://api.qidong.autos' if supplier=='qidong' else 'https://cf.api.fan'
  key='local-fake-only' if cid==2 or not enabled else keys['qidong' if supplier=='qidong' else 'Packy']
  rec={**template,'id':cid,'name':f'canvas-{supplier}-{variant}','key':key,'base_url':url,'status':1 if enabled else 2,'models':alias,'model_mapping':json.dumps({alias:'gpt-image-2.5-'+variant}),'priority':priority,'other_info':'{}'}
  db.execute('insert or replace into channels ('+','.join('"'+k+'"' for k in rec)+') values ('+','.join('?' for k in rec)+')',tuple(rec.values()));db.execute('delete from abilities where channel_id=?',(cid,));db.execute('insert into abilities ("group",model,channel_id,enabled,priority,weight) values (?,?,?,?,?,100)',('canvas-image',alias,cid,enabled,priority))
 for k,add in [('ModelPrice',{'canvas-image':.03,'canvas-image-sunburst':.03,'canvas-qidong-flare':.03,'canvas-qidong-sunburst':.03}),('ModelRatio',{'canvas-packy-flare':12.5,'canvas-packy-sunburst':12.5}),('CompletionRatio',{'canvas-packy-flare':6,'canvas-packy-sunburst':6}),('ImageRatio',{'canvas-packy-flare':1.6,'canvas-packy-sunburst':1.6})]:
  row=db.execute('select value from options where key=?',(k,)).fetchone();v=json.loads(row[0]) if row else {};v.update(add)
  if k=='ModelPrice':v.pop('canvas-packy-flare',None);v.pop('canvas-packy-sunburst',None)
  db.execute('insert or replace into options (key,value) values (?,?)',(k,json.dumps(v)))
 token=secrets.token_hex(24);db.execute("update tokens set key=?,status=1,remain_quota=1795000,used_quota=0,unlimited_quota=0,expired_time=?,model_limits_enabled=1,model_limits='canvas-image,canvas-image-sunburst',allow_ips=NULL where id=4",(token,int(time.time())+86400));db.execute('update users set quota=1795000,used_quota=0 where id=3');db.commit();db.close();(out/'test.token').write_text('sk-'+token)
 oldgw=inspect('new-api-personal');env=[e for e in oldgw['Config']['Env'] if not e.startswith(('SQL_DSN=','SQLITE_PATH=','CANVAS_IMAGE_','CHANNEL_TEST_ENABLED=','ERROR_LOG_ENABLED='))]+['SQLITE_PATH=/data/new-api.db','CANVAS_IMAGE_ROUTING_ENABLED=true','CANVAS_IMAGE_AMBIGUOUS_FAILOVER_ENABLED=false','CANVAS_IMAGE_PRIMARY_TIMEOUT_SECONDS=180','CANVAS_IMAGE_BACKUP_TIMEOUT_SECONDS=240','CHANNEL_TEST_ENABLED=false','ERROR_LOG_ENABLED=true']
 create(gateway,{'Image':'new-api:canvas-autofailover-candidate','Env':env,'HostConfig':{'Binds':[str(data)+':/data'],'PortBindings':{'3000/tcp':[{'HostIp':'127.0.0.1','HostPort':'13057'}]}},'NetworkingConfig':{'EndpointsConfig':{net:{}}}});wait('http://127.0.0.1:13057/api/status')
 # Copy the existing acceptance database, including already verified reference-media identities.
 exists=run(['docker','exec','canvas-migrated-postgres','sh','-c',"psql -U \"$POSTGRES_USER\" -d postgres -Atc \"select 1 from pg_database where datname='"+database+"'\""]).strip();assert not exists,'Existing paid database; no replay'
 dump=run(['docker','exec','canvas-migrated-postgres','sh','-c','pg_dump -U "$POSTGRES_USER" -d canvas_newapi_acceptance_20261016 -Fc']);(out/'acceptance-baseline.dump').write_bytes(dump)
 run(['docker','exec','canvas-migrated-postgres','sh','-c','createdb -U "$POSTGRES_USER" '+database]);run(['docker','exec','-i','canvas-migrated-postgres','sh','-c','pg_restore -U "$POSTGRES_USER" -d '+database+' --no-owner'],dump)
 run(['docker','cp','canvas-newapi-api-staging:/tmp/canvas-acceptance-private.json',str(out/'credentials-private.json')]);creds=json.loads((out/'credentials-private.json').read_text())
 oldapi=inspect('canvas-newapi-api-staging');env=dict(e.split('=',1) for e in oldapi['Config']['Env'] if '=' in e);url=urllib.parse.urlsplit(env['DATABASE_URL']);env['DATABASE_URL']=urllib.parse.urlunsplit((url.scheme,url.netloc,'/'+database,url.query,url.fragment))
 create(canvas,{'Image':'infinite-canvas-api:autofailover-candidate-20261016','Env':[k+'='+v for k,v in env.items()],'HostConfig':{'Binds':oldapi['HostConfig'].get('Binds',[]),'PortBindings':{'3001/tcp':[{'HostIp':'127.0.0.1','HostPort':'13058'}]}},'NetworkingConfig':{'EndpointsConfig':{net:{}}}});wait('http://127.0.0.1:13058/health');run(['docker','cp',str(out/'test.token'),canvas+':/tmp/af.token'])
 js="""import{readFileSync}from'node:fs';import{randomUUID}from'node:crypto';import{sqlClient as s,db,closeDatabase}from'/app/dist/db/client.js';import*as schema from'/app/dist/db/schema.js';import{encryptSecret}from'/app/dist/crypto.js';const channelId=randomUUID(),sunId=randomUUID();await s`update models set status='draft' where capability='image'`;await db.insert(schema.channels).values({id:channelId,name:'New API主备验收',protocol:'openai',baseUrl:'http://canvas-af-paid-gateway:3000/v1',encryptedApiKey:encryptSecret(readFileSync('/tmp/af.token','utf8').trim()),status:'active',timeoutMs:480000,maxConcurrency:1,cooldownSeconds:0});const flareId='FLARE';await s`update models set name='canvas-image',display_name='GPT Image 2.5 Flare',status='published',sort_order=-100 where id=${flareId}`;await s`update model_channels set enabled=false where model_id=${flareId}`;await db.insert(schema.modelChannels).values({modelId:flareId,channelId,upstreamModel:'canvas-image',priority:100,enabled:true});await db.insert(schema.models).values({id:sunId,name:'canvas-image-sunburst',displayName:'GPT Image 2.5 Sunburst',capability:'image',status:'published',sortOrder:-90,config:{routing:'newapi'}});await db.insert(schema.modelChannels).values({modelId:sunId,channelId,upstreamModel:'canvas-image-sunburst',priority:100,enabled:true});await s`update users set must_change_password=false where id='USER'`;console.log(JSON.stringify({flareId,sunId,channelId,published:await s`select id,name,display_name from models where capability='image' and status='published'`}));await closeDatabase();""".replace('FLARE',creds['modelId']).replace('USER',creds['userId'])
 models=node(js,canvas);(out/'models.json').write_text(json.dumps(models));(out/'prepared.json').write_text(json.dumps({'at':time.time(),'counts':counts,'paidSends':0,'budget':{'CNY':.03,'USDReserve':3.56},'PackyBalancePositive':True,'models':models},ensure_ascii=False,indent=2));print(json.dumps({'prepared':True,'realSends':0,'employeeModels':[x['display_name'] for x in models['published']]}))
def execute(which):
 assert(out/'prepared.json').exists() and not(out/'STOP.json').exists()
 if which=='two':assert json.loads((out/'one-result.json').read_text())['status']=='succeeded'
 assert not(out/(which+'-intent.json')).exists(),'Durable intent exists; do not replay even if result is unknown'
 if not inspect(canvas)['State']['Running']:raise RuntimeError('Fixture stopped')
 creds=json.loads((out/'credentials-private.json').read_text());models=json.loads((out/'models.json').read_text());original=json.loads((oldroot/'paid-acceptance/results.json').read_text());ref=original[0]['task']['image']['mediaId']
 jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));base='http://127.0.0.1:13058'
 def api(path,data=None):
  req=urllib.request.Request(base+path,data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None,headers={'Content-Type':'application/json'})
  with opener.open(req,timeout=30) as r:return json.load(r)
 api('/api/auth/login',{'username':creds['username'],'password':creds['password']})
 server=None
 if which=='two':
  class Stub(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    self.rfile.read(int(self.headers.get('Content-Length','0')));body=b'{"error":{"message":"synthetic pre-accept authentication failure","type":"invalid_request_error","code":"invalid_api_key"}}';self.send_response(401);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  server=http.server.ThreadingHTTPServer(((out/'host.txt').read_text().strip(),13059),Stub);threading.Thread(target=server.serve_forever,daemon=True).start()
 request={'modelId':models['sunId' if which=='one' else 'flareId'],'prompt':'以参考图为基础，保留杯子、桌面、绿叶和黄色圆形标记，把杯子改成绿色。保持3:4竖版。','count':1,'parameters':{'size':'768x1024'},'referenceMediaIds':[ref]}
 (out/(which+'-intent.json')).write_text(json.dumps({'at':time.time(),'request':request,'maximumRealSends':1,'supplier':'qidong' if which=='one' else 'Packy'},ensure_ascii=False,indent=2))
 try:
  created=api('/api/generation-batches',request);task=created['tasks'][0];record={'operation':which,'taskId':task['id'],'batchId':created['batch']['id'],'referenceCount':1,'status':'submitted'};(out/(which+'-result.json')).write_text(json.dumps(record));print(json.dumps(record),flush=True)
  deadline=time.monotonic()+520
  while time.monotonic()<deadline:
   batch=api('/api/generation-batches/'+record['batchId']);task=next(t for t in batch['tasks'] if t['id']==record['taskId'])
   if task['status'] in ['succeeded','failed']:break
   time.sleep(2)
  record.update(task=task,status=task['status']);(out/(which+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2));assert task['status']=='succeeded','First failure or unknown, stop'
  with opener.open(base+task['image']['url'],timeout=30) as r:img=r.read()
  assert img[:8]==b'\x89PNG\r\n\x1a\n' and task['image']['width']*4==task['image']['height']*3
  (out/(which+'.png')).write_bytes(img);record['imageSHA256']=hashlib.sha256(img).hexdigest()
  js="import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';const[r]=await s`select id,task_id,gateway_request_id,upstream_request_id,gateway_evidence from request_logs where task_id='"+record['taskId']+"'`;console.log(JSON.stringify(r));await closeDatabase();"
  record['canvasLog']=node(js,canvas);rid=record['canvasLog']['gateway_request_id'];assert rid
  token=(out/'test.token').read_text().strip();logs=fetch('http://127.0.0.1:13057/api/log/token?request_id='+urllib.parse.quote(rid),token)['data'];rows=[r for r in logs if r['request_id']==rid];consumed=[r for r in rows if r['type']==2];assert len(consumed)==1 and consumed[0]['channel']==(4 if which=='one' else 3)
  record['newApiAttempts']=[{k:r.get(k) for k in ['request_id','upstream_request_id','channel','model_name','quota','type','created_at','other']} for r in rows]
  if which=='one':
   assert consumed[0]['quota']==15000;key=(oldroot/'secrets/qidong-image.key').read_text().strip();bill=fetch('https://api.qidong.autos/api/log/token',key);match=[r for r in bill['data'] if r.get('request_id')==consumed[0]['upstream_request_id'] and r.get('type')==2];assert len(match)==1 and match[0]['model_name']=='gpt-image-2.5-sunburst' and match[0]['quota']==15000
   record['supplierBill']={'requestId':match[0]['request_id'],'model':match[0]['model_name'],'accountDebitCNY':.03,'source':'https://api.qidong.autos/api/log/token','snapshotSHA256':hashlib.sha256(json.dumps(match[0],sort_keys=True).encode()).hexdigest()}
  else:
   assert len(rows)==2 and any(r['type']==5 and r['channel']==2 and r['quota']==0 for r in rows),'Expected failed fake primary and successful Packy only'
   record['supplierBill']={'status':'pending_verification','currency':'USD','amount':None,'reason':'Supplier token log does not expose unique bill; no invented amount'}
  (out/(which+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps({'operation':which,'status':record['status'],'taskId':record['taskId'],'gatewayRequestId':rid,'pixels':[task['image']['width'],task['image']['height']],'attempts':len(rows),'platformQuota':consumed[0]['quota'],'supplierBill':record['supplierBill']},ensure_ascii=False),flush=True)
 finally:
  if server:server.shutdown()
  try:api('/api/auth/logout',{})
  except Exception:pass
if __name__=='__main__':
 try:
  if sys.argv[1]=='prepare':prepare()
  elif sys.argv[1] in ['one','two']:execute(sys.argv[1])
  else:raise RuntimeError('Unknown command')
 except Exception as e:
  (out/'STOP.json').write_text(json.dumps({'at':time.time(),'operation':sys.argv[1],'exception':type(e).__name__,'reason':str(e)[:400]}));print(json.dumps({'STOP':True,'exception':type(e).__name__,'reason':str(e)[:250]}),flush=True);raise
