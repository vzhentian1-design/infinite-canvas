"""Read-only reconciliation; stop own acceptance containers, never resend."""
import datetime,json,pathlib,sqlite3,subprocess,urllib.request,os
os.umask(0o077);root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016');out=root/'paid'
db=sqlite3.connect('file:'+str(out/'data/new-api.db')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
rows=[dict(r) for r in db.execute('select * from logs order by id')];key=db.execute('select key from channels where id=3').fetchone()[0];db.close()
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':'Bearer '+key,'User-Agent':'Mozilla/5.0'}),timeout=20) as r:return json.load(r)
balance=get('https://www.packyapi.com/api/usage/token');bill=get('https://www.packyapi.com/api/log/token');prior=json.loads((out/'provider-check-private.json').read_text())['balance'];(out/'provider-after-private.json').write_text(json.dumps({'balance':balance,'bill':bill}))
attempts=[]
for r in rows:
 other=json.loads(r['other']);attempts.append({'gatewayRequestId':r['request_id'],'supplierRequestId':r.get('upstream_request_id') or None,'supplier':other.get('image_supplier'),'model':other.get('upstream_model_name'),'attempt':other.get('image_attempt'),'type':r['type'],'platformQuota':r['quota'],'httpStatus':other.get('status_code',200 if r['type']==2 else None),'errorCode':other.get('error_code'),'supplierEstimate':other.get('supplier_estimate'),'supplierCharge':other.get('supplier_charge'),'synthetic':r['channel_id']==2})
one=json.loads((out/'one-result.json').read_text());two=json.loads((out/'two-result.json').read_text())
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'authorizedRealSupplierSends':2,'actualRealSupplierSends':2,'syntheticPrimaryFailures':1,'additionalPaidSends':0,'qidongSunburst':{'status':one['status'],'taskId':one['taskId'],'pixels':[one['task']['image']['width'],one['task']['image']['height']],'supplierBill':one['supplierBill']},'packyFlare':{'status':two['status'],'taskId':two['taskId'],'errorCode':two['task']['errorCode'],'errorMessage':two['task']['errorMessage'],'platformQuota':0,'supplierAmount':None,'supplierBillingStatus':'pending_verification'},'attempts':attempts,'PackyBalanceUnchangedObserved':prior['data']['total_available']==balance['data']['total_available'],'PackyTokenLogMessage':bill.get('message'),'balanceObservationDoesNotProveIndividualZeroDebit':True,'paidStopGuardPresent':(out/'STOP.json').exists(),'productionChanged':False}
assert len(rows)==3 and [r['quota'] for r in rows]==[15000,0,0]
for name in ['canvas-af-paid-api','canvas-af-paid-gateway']:subprocess.check_call(['docker','stop',name],stdout=subprocess.DEVNULL)
result['acceptanceContainersStopped']=True
(out/'safe-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
