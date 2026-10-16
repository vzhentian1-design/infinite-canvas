"""Isolated native gateway with synthetic keys, two models and local upstreams."""
import base64, copy, datetime, email, email.policy, hashlib, http.server, json, os, pathlib, secrets, sqlite3, subprocess, threading, time, urllib.request, urllib.error, uuid
os.umask(0o077)
root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016/protocol-fix-free'); stage=root/'free'; (stage/'data').mkdir(mode=0o700,parents=True,exist_ok=True)
def run(args,data=None):return subprocess.check_output(args,input=data,stderr=subprocess.PIPE)
def inspect(n):return json.loads(run(['docker','inspect',n]))[0]
assert subprocess.run(['docker','inspect','canvas-af-protocol-free'],capture_output=True).returncode!=0,'Existing fixture; inspect before reuse'
api=inspect('canvas-migrated-api');network=next(iter(api['NetworkSettings']['Networks']))
gateway=json.loads(run(['docker','network','inspect',network]))[0]['IPAM']['Config'][0]['Gateway']
source=sqlite3.connect('file:/opt/new-api/data/new-api.db?mode=ro',uri=True);db=sqlite3.connect(str(stage/'data/new-api.db'));source.backup(db);source.close();db.row_factory=sqlite3.Row
db.execute("update channels set key='synthetic-only',status=2,base_url='http://127.0.0.1:1'");db.execute('update abilities set enabled=0')
template=dict(db.execute('select * from channels where id=2').fetchone())
specs=[(2,'qidong','flare',100),(3,'packy','flare',10),(4,'qidong','sunburst',100),(5,'packy','sunburst',10)]
for cid,supplier,variant,priority in specs:
    alias='canvas-image' if variant=='flare' else 'canvas-image-sunburst'
    record={**template,'id':cid,'name':f'canvas-{supplier}-{variant}','key':'synthetic-only','base_url':f'http://{gateway}:13056/{supplier}/{variant}','status':1,'models':alias,'model_mapping':json.dumps({alias:'gpt-image-2.5-'+variant}),'priority':priority,'other_info':'{}'}
    db.execute('insert or replace into channels ('+','.join('"'+k+'"' for k in record)+') values ('+','.join('?' for k in record)+')',tuple(record.values()))
    db.execute('delete from abilities where channel_id=?',(cid,));db.execute('insert into abilities ("group",model,channel_id,enabled,priority,weight) values (?,?,?,1,?,100)',('canvas-image',alias,cid,priority))
for key,entries in [('ModelPrice',{'canvas-image':.03,'canvas-image-sunburst':.03,'canvas-qidong-flare':.03,'canvas-qidong-sunburst':.03}),('ModelRatio',{'canvas-packy-flare':12.5,'canvas-packy-sunburst':12.5}),('CompletionRatio',{'canvas-packy-flare':6,'canvas-packy-sunburst':6}),('ImageRatio',{'canvas-packy-flare':1.6,'canvas-packy-sunburst':1.6})]:
    old=db.execute('select value from options where key=?',(key,)).fetchone();data=json.loads(old[0]) if old else {};data.update(entries)
    if key=='ModelPrice':data.pop('canvas-packy-flare',None);data.pop('canvas-packy-sunburst',None)
    db.execute('insert or replace into options (key,value) values (?,?)',(key,json.dumps(data)))
db.execute('update users set quota=50000000 where id=3'); token=secrets.token_hex(24)
db.execute("update tokens set key=?,remain_quota=50000000,allow_ips=NULL,model_limits='canvas-image,canvas-image-sunburst',status=1 where id=4",(token,));db.commit();db.close()
(stage/'Dockerfile').write_text('FROM new-api:rc44-canvas-images-20261016\nCOPY new-api-canvas-autofailover /new-api\nRUN chmod 755 /new-api\n')
run(['cp',str(root/'new-api-canvas-autofailover'),str(stage/'new-api-canvas-autofailover')]);(stage/'build.log').write_bytes(run(['docker','build','-t','new-api:canvas-autofailover-protocolfix',str(stage)]))
run(['docker','create','--name','canvas-af-protocol-free','--network',network,'-p','127.0.0.1:13054:3000','-v',str(stage/'data')+':/data','-e','SQLITE_PATH=/data/new-api.db','-e','CANVAS_IMAGE_ROUTING_ENABLED=true','-e','CANVAS_IMAGE_AMBIGUOUS_FAILOVER_ENABLED=true','-e','CANVAS_IMAGE_PRIMARY_TIMEOUT_SECONDS=1','-e','CANVAS_IMAGE_BACKUP_TIMEOUT_SECONDS=2','-e','CHANNEL_TEST_ENABLED=false','-e','CRITICAL_RATE_LIMIT_ENABLE=false','new-api:canvas-autofailover-protocolfix'])
state={'mode':{},'calls':[]};png='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+y8akAAAAASUVORK5CYII='
class Stub(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        _,supplier,variant,*_=self.path.split('/');raw=self.rfile.read(int(self.headers.get('Content-Length','0')));kind=self.headers.get('Content-Type','');fields={};refs=0
        if 'multipart/' in kind:
            msg=email.message_from_bytes(('Content-Type: '+kind+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw,policy=email.policy.default)
            for part in msg.iter_parts():
                name=part.get_param('name',header='content-disposition')
                if part.get_filename():refs+=1
                else:fields[name]=part.get_content()
        else:fields=json.loads(raw)
        state['calls'].append({'supplier':supplier,'variant':variant,'model':fields.get('model'),'response_format':fields.get('response_format'),'quality':fields.get('quality'),'refs':refs,'n':str(fields.get('n')),'size':fields.get('size')})
        scenario=state['mode'].get((supplier,variant),'ok')
        if scenario=='drop':self.connection.close();return
        if scenario=='timeout':time.sleep(1.5);self.connection.close();return
        status=200 if scenario=='ok' else 503 if scenario=='safety' else int(scenario)
        body={'data':[{'b64_json':png}],'usage':{'input_tokens':9,'output_tokens':196,'total_tokens':205}} if status==200 else {'error':{'message':'safety refusal' if scenario=='safety' else 'synthetic failure','type':'invalid_request_error','code':'content_policy_violation' if scenario=='safety' else str(status)}}
        data=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('X-Oneapi-Request-Id','fixture-'+uuid.uuid4().hex);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
server=http.server.ThreadingHTTPServer((gateway,13056),Stub);threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:13054'
def ready():
    for _ in range(60):
        try:
            with urllib.request.urlopen(base+'/api/status',timeout=2) as r:assert r.status==200
            return
        except Exception:time.sleep(.25)
    raise RuntimeError('Fixture health failed')
run(['docker','start','canvas-af-protocol-free']);ready()
def expire(cid):
    db=sqlite3.connect(str(stage/'data/new-api.db'));raw=db.execute('select other_info from channels where id=?',(cid,)).fetchone()[0];info=json.loads(raw);info['status_time']=int(time.time())-360;db.execute('update channels set other_info=? where id=?',(json.dumps(info),cid));db.commit();db.close()
def call(label,variant,mode,expected,refs=0,backup='ok',http=200):
    state['mode'][('qidong',variant)]=mode;state['mode'][('packy',variant)]=backup;state['calls']=[];alias='canvas-image' if variant=='flare' else 'canvas-image-sunburst'
    if refs:
        boundary=uuid.uuid4().hex;parts=[]
        for name,value in [('model',alias),('prompt','synthetic fixture'),('size','768x1024'),('quality','high'),('n','1'),('response_format','b64_json')]:parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for i in range(refs):parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="ref{i}.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+base64.b64decode(png)+b'\r\n')
        data=b''.join(parts)+f'--{boundary}--\r\n'.encode();content='multipart/form-data; boundary='+boundary;path='/v1/images/edits'
    else:data=json.dumps({'model':alias,'prompt':'synthetic fixture','n':1,'size':'768x1024','quality':'high','response_format':'b64_json'}).encode();content='application/json';path='/v1/images/generations'
    req=urllib.request.Request(base+path,data=data,headers={'Authorization':'Bearer sk-'+token,'Content-Type':content,'X-Canvas-Task-Id':str(uuid.uuid4())})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:status=r.status;payload=json.load(r);rid=r.headers.get('X-Oneapi-Request-Id')
    except urllib.error.HTTPError as e:status=e.code;payload=json.load(e);rid=e.headers.get('X-Oneapi-Request-Id')
    assert status==http,(label,status,payload)
    assert [r['supplier'] for r in state['calls']]==expected,(label,state['calls'])
    assert len(state['calls'])<=2
    for r in state['calls']:
        assert r['model']=='gpt-image-2.5-'+variant and r['refs']==refs and r['n']=='1' and r['size']=='768x1024',r
        assert r['quality']==('low' if r['supplier']=='packy' else None),r
        assert r['response_format']==(None if r['supplier']=='packy' else 'b64_json'),r
    # Use the same scoped native log API that Canvas's settlement poll consumes.
    req=urllib.request.Request(base+'/api/log/token?request_id='+rid,headers={'Authorization':'Bearer sk-'+token})
    for _ in range(30):
        with urllib.request.urlopen(req,timeout=25) as r:logs=json.load(r)['data']
        if len(logs)==len(expected):break
        time.sleep(.25)
    assert len(logs)==len(expected),(label,'missing attempt log',logs)
    known=[x['upstream_request_id'] for x in logs if x.get('upstream_request_id')]
    assert len(set(known))==len(known),'Receipt leaked between attempts'
    if mode in ('drop','timeout') and len(expected)==2:
        assert not next(x for x in logs if x['type']==5).get('upstream_request_id'),'Unknown receipt inherited an earlier identity'
    result={'case':label,'http':status,'requestId':rid,'calls':list(state['calls']),'logs':[{'request_id':x.get('request_id'),'upstream_request_id':x.get('upstream_request_id'),'type':x['type'],'quota':x['quota'],'channel':x['channel'],'other':x['other']} for x in logs],'PASS':True}
    (root/'free-gateway-progress.json').write_text(json.dumps({'realSupplierRequests':0,'results':results+[result]},indent=2))
    return result
results=[]
try:
    for variant,cid in [('flare',2),('sunburst',4)]:
        results.append(call(variant+'_healthy',variant,'ok',['qidong']))
        results.append(call(variant+'_503_same_request_backup',variant,'503',['qidong','packy']))
        results.append(call(variant+'_cooldown_routes_next',variant,'503',['packy']))
        other='sunburst' if variant=='flare' else 'flare'
        results.append(call(variant+'_other_model_independent',other,'ok',['qidong']))
        expire(cid);results.append(call(variant+'_real_request_recovery',variant,'ok',['qidong']))
        results.append(call(variant+'_single_reference',variant,'ok',['qidong'],refs=1))
        results.append(call(variant+'_dual_reference_backup',variant,'503',['qidong','packy'],refs=2))
        expire(cid);results.append(call(variant+'_safety_never_switches',variant,'safety',['qidong'],http=503))
        results.append(call(variant+'_400_never_switches',variant,'400',['qidong'],http=400))
        results.append(call(variant+'_disconnect_backup',variant,'drop',['qidong','packy']))
        expire(cid);results.append(call(variant+'_both_fail_at_most_two',variant,'503',['qidong','packy'],backup='503',http=503))
        expire(cid);expire(3 if variant=='flare' else 5)
        results.append(call(variant+'_timeout_reserves_backup_time',variant,'timeout',['qidong','packy']))
        expire(cid)
    result={'observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'realSupplierRequests':0,'passed':len(results),'results':results}
    (root/'free-gateway.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':len(results),'realSupplierRequests':0}))
finally:
    server.shutdown();server.server_close();run(['docker','stop','canvas-af-protocol-free'])
