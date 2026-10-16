"""Free production readback, preserve all paid evidence and stopped test fixtures."""
import datetime,hashlib,json,os,pathlib,sqlite3,subprocess,urllib.request
os.umask(0o077);root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016');rel=root/'release-r2'
def run(a,data=None):return subprocess.check_output(a,input=data,stderr=subprocess.PIPE)
def inspect(n):return json.loads(run(['docker','inspect',n]))[0]
db=sqlite3.connect('file:/opt/new-api/data/new-api.db?mode=ro',uri=True);db.row_factory=sqlite3.Row
options={r['key']:r['value'] for r in db.execute('select * from options')};assert options['RetryTimes']=='0'
price={k:json.loads(options.get(k) or '{}') for k in ['ModelPrice','ModelRatio','CompletionRatio','ImageRatio']}
for variant in ['flare','sunburst']:
 assert price['ModelPrice']['canvas-qidong-'+variant]==.03 and 'canvas-packy-'+variant not in price['ModelPrice']
 assert price['ModelRatio']['canvas-packy-'+variant]==12.5 and price['CompletionRatio']['canvas-packy-'+variant]==6 and price['ImageRatio']['canvas-packy-'+variant]==1.6
token=(pathlib.Path('/opt/canvas-newapi-integration-20261016/secrets/canvas-image-production.token')).read_text().strip()
req=urllib.request.Request('http://127.0.0.1:3044/v1/models',headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(req,timeout=10) as r:models=json.load(r)
assert {r['id'] for r in models['data']}=={'canvas-image','canvas-image-sunburst'}
env=dict(v.split('=',1) for v in inspect('new-api-personal')['Config']['Env'] if '=' in v)
assert env['CANVAS_IMAGE_AMBIGUOUS_FAILOVER_ENABLED']=='true' and env['CANVAS_IMAGE_PRIMARY_TIMEOUT_SECONDS']=='180' and env['CANVAS_IMAGE_BACKUP_TIMEOUT_SECONDS']=='240' and env['CANVAS_IMAGE_FLARE_COOLDOWN_SECONDS']==env['CANVAS_IMAGE_SUNBURST_COOLDOWN_SECONDS']=='300'
health={}
for url in ['https://canvas.dongyuanhub.com/','http://127.0.0.1:13001/health','http://127.0.0.1:3044/api/status']:
 with urllib.request.urlopen(url,timeout=10) as r:health[url]=r.status
assert all(v==200 for v in health.values())
fixed=json.loads((root/'paid/protocol-fix-once/two-result.json').read_text());one=json.loads((root/'paid/one-result.json').read_text())
summary={'actualRealSupplierSends':3,'qidongSuccessful':1,'PackyRejected400':1,'PackySuccessfulAfterSeparateApproval':1,'qidongCNY':.03,'PackyDebitStatus':'pending_verification','qidongTaskId':one['taskId'],'PackyTaskId':fixed['taskId'],'attempts':[]}
for label,path in [('qidong',root/'paid/one-result.json'),('Packy-fixed',root/'paid/protocol-fix-once/two-result.json')]:
 v=json.loads(path.read_text())
 for row in v['newApiAttempts']:
  other=json.loads(row['other']);summary['attempts'].append({'case':label,'gatewayRequestId':row['request_id'],'supplierRequestId':row['upstream_request_id'],'supplier':other.get('image_supplier'),'model':other.get('upstream_model_name'),'attempt':other.get('image_attempt'),'platformQuota':row['quota'],'type':row['type'],'supplierEstimate':other.get('supplier_estimate'),'supplierCharge':other.get('supplier_charge')})
assert next(x['platformQuota'] for x in summary['attempts'] if x['supplier']=='canvas-packy-flare')==39753
testnames=['canvas-af-paid-api','canvas-af-paid-gateway','canvas-af-paid-gateway-pre-protocolfix','canvas-af-protocol-free'];stopped={n:not inspect(n)['State']['Running'] for n in testnames};assert all(stopped.values())
completed=json.loads((rel/'completed.json').read_text());completed.update(health=health,nativeModelDirectory200=True,pricesVerified=True,globalRetryTimes=0,testContainersStopped=stopped,realAcceptance=summary,gatewayBinarySha256=hashlib.sha256((root/'protocol-fix-free/new-api-canvas-autofailover').read_bytes()).hexdigest(),rollbackDryRun='PASS')
completed['employeeUi']='Production shared selector read back in existing admin browser session; only two options, Flare default, switched to Sunburst and back without generation; real acceptance used normal-user API in isolated Canvas DB'
(root/'published-safe.json').write_text(json.dumps(completed,ensure_ascii=False,indent=2));print(json.dumps({'deployed':True,'health':health,'gatewayAliases':list(sorted(r['id'] for r in models['data'])),'priceRules':'PASS','actualRealSupplierSends':3,'PackySuccessQuota':39753,'PackyDebit':'pending_verification','testContainersStopped':stopped},ensure_ascii=False))
