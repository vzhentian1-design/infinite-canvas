"""Owner separately approved exactly one additional Packy Flare send."""
import importlib.util,json,pathlib,shutil,sqlite3,time
spec=importlib.util.spec_from_file_location('paid_minimal','/opt/canvas-newapi-autofailover-20261016/paid_minimal.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
prior=m.out;fix=prior/'protocol-fix-once';fix.mkdir(mode=0o700,exist_ok=True)
assert not(fix/'authorization-started.json').exists(),'This separate authorization must never replay'
assert(prior/'STOP.json').exists() and json.loads((prior/'two-result.json').read_text())['status']=='failed'
assert not m.inspect(m.gateway)['State']['Running'] and not m.inspect(m.canvas)['State']['Running']
db=sqlite3.connect(str(prior/'data/new-api.db'));db.row_factory=sqlite3.Row
key=db.execute('select key from channels where id=3').fetchone()[0]
balance=m.fetch('https://www.packyapi.com/api/usage/token',key);assert balance.get('message')=='ok' and balance['data']['total_available']>0
prices=m.fetch('https://www.packyapi.com/api/pricing');p=next(x for x in prices['data'] if x['model_name']=='gpt-image-2.5-flare');assert p['model_ratio']==2.5 and p['completion_ratio']==6 and p['image_ratio']==1.6 and prices['group_ratio']['image']==5
db.execute("update channels set status=1,other_info='{}' where id in (2,3)");db.execute('update channels set status=2 where id in (4,5)');db.execute('update abilities set enabled=case when channel_id in (2,3) then 1 else 0 end');db.execute("update tokens set model_limits='canvas-image' where id=4");db.commit();db.close()
old=m.inspect(m.gateway);cfg={k:old['Config'][k] for k in ['Env']};cfg['Image']='new-api:canvas-autofailover-protocolfix';cfg['HostConfig']=old['HostConfig'];cfg['NetworkingConfig']={'EndpointsConfig':{n:{} for n in old['NetworkSettings']['Networks']}}
m.run(['docker','rename',m.gateway,m.gateway+'-pre-protocolfix']);m.create(m.gateway,cfg);m.wait('http://127.0.0.1:13057/api/status');m.run(['docker','start',m.canvas]);m.wait('http://127.0.0.1:13058/health')
for name in ['prepared.json','one-result.json','credentials-private.json','models.json','host.txt','test.token']:shutil.copy2(prior/name,fix/name)
(fix/'authorization-started.json').write_text(json.dumps({'at':time.time(),'maximumAdditionalRealSends':1,'supplier':'Packy','model':'gpt-image-2.5-flare','USDReserve':3.56,'noAutomaticRetryOrTopUp':True,'ownerReply':'批准补 1 次 Packy Flare'}))
m.out=fix
try:m.execute('two')
except Exception as e:
 (fix/'STOP.json').write_text(json.dumps({'exception':type(e).__name__,'reason':str(e)[:300]}));raise
finally:
 for name in [m.canvas,m.gateway]:m.run(['docker','stop',name])
