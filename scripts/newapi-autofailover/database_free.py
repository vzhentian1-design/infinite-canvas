"""Real disposable MySQL/PostgreSQL, no changes to project database instances."""
import json,os,pathlib,secrets,subprocess,time
os.umask(0o077);root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016');p=root/'database-free';p.mkdir(mode=0o700,exist_ok=True)
def run(a,data=None):
    r=subprocess.run(a,input=data,capture_output=True)
    if r.returncode:
        (p/'last-error-private.log').write_bytes(r.stdout+r.stderr)
        raise RuntimeError('Fixture operation failed; inspect protected last-error-private.log')
    return r.stdout
network=json.loads(run(['docker','inspect','canvas-migrated-api']))[0]['NetworkSettings']['Networks'];network=next(iter(network))
password=(p/'mysql.env').read_text().splitlines()[0].split('=',1)[1] if (p/'mysql.env').exists() else secrets.token_hex(24)
(p/'postgres.env').write_text('POSTGRES_PASSWORD='+password+'\nPOSTGRES_DB=canvas_policy\n')
(p/'mysql.env').write_text('MYSQL_ROOT_PASSWORD='+password+'\nMYSQL_DATABASE=canvas_policy\n')
names=['canvas-af-postgres','canvas-af-mysql'];results=[]
for name,image,env in [(names[0],'postgres:latest','postgres.env'),(names[1],'mysql:8.0','mysql.env')]:
    existing=subprocess.run(['docker','inspect',name],capture_output=True)
    if existing.returncode==0:
        info=json.loads(existing.stdout)[0]
        assert info['Config']['Image']==image and any(e.endswith('='+password) for e in info['Config']['Env']),'Unrelated fixture identity'
        if not info['State']['Running']:run(['docker','start',name])
    else:run(['docker','run','-d','--name',name,'--network',network,'--env-file',str(p/env),image]+(['--character-set-server=utf8mb4','--collation-server=utf8mb4_unicode_ci'] if name.endswith('mysql') else []))
try:
    for name in names:
        check=['docker','exec',name,'pg_isready','-U','postgres'] if name.endswith('postgres') else ['docker','exec',name,'sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin ping -h 127.0.0.1 --silent']
        for _ in range(90):
            if subprocess.run(check,capture_output=True).returncode==0:break
            time.sleep(.5)
        else:raise RuntimeError('Database readiness failed')
    pgdsn='postgres://postgres:'+password+'@canvas-af-postgres:5432/canvas_policy?sslmode=disable'
    for engine,dsn in [('sqlite',None),('postgres',pgdsn),('mysql','root:'+password+'@tcp(canvas-af-mysql:3306)/canvas_policy?charset=utf8mb4&parseTime=True&loc=Local')]:
        envfile=p/(engine+'-test.env');envfile.write_text('CANVAS_POLICY_DATABASE_DSN='+dsn+'\n' if dsn else '')
        output=run(['docker','run','--rm','--network',network,'--env-file',str(envfile),'-v',str(root/'service.test')+':/service.test:ro','--entrypoint','/service.test','new-api:rc44-canvas-images-20261016','-test.run','^TestCanvasImageNativeCooldownPersistsAndRecoversOnDemand$','-test.v'])
        (p/(engine+'.log')).write_bytes(output);assert b'PASS' in output
        results.append({'engine':engine,'cooldownRecoveryAndTokenIsolation':'PASS'})
    # The Canvas code runs only an isolated Node script, never the worker/server.
    run(['docker','exec','canvas-af-postgres','createdb','-U','postgres','canvas_settlement'])
    (p/'canvas.env').write_text('DATABASE_URL='+pgdsn.replace('/canvas_policy?','/canvas_settlement?')+'\nCHANNEL_ENCRYPTION_KEY='+secrets.token_hex(32)+'\nMINIO_ENDPOINT=localhost\nMINIO_ACCESS_KEY=synthetic\nMINIO_SECRET_KEY=synthetic-only\nNODE_ENV=test\n')
    # Import from /app/dist so compiled relative imports resolve through the
    # existing deployed modules; only the two modified modules are overlaid.
    script=(root/'settlement_pg.mjs').read_text().replace('/candidate/','/app/dist/')
    run(['docker','create','--name','canvas-af-pg-query-run','--network',network,'--env-file',str(p/'canvas.env'),'--entrypoint','node','infinite-canvas-api:newapi-images-20261016','/app/settlement_pg.mjs'])
    for f in ['newapi-evidence.js','newapi-settlement.js']:run(['docker','cp',str(root/'canvas-dist'/f),'canvas-af-pg-query-run:/app/dist/'+f])
    (p/'settlement-run.mjs').write_text(script);run(['docker','cp',str(p/'settlement-run.mjs'),'canvas-af-pg-query-run:/app/settlement_pg.mjs'])
    output=run(['docker','start','-a','canvas-af-pg-query-run']);(p/'canvas-pg.log').write_bytes(output)
    assert b'"PASS":true' in output, 'Canvas query did not pass'
    results.append(json.loads(output.decode().strip().splitlines()[-1]));(root/'database-free.json').write_text(json.dumps({'results':results,'productionDatabaseWrites':0},indent=2));print(json.dumps({'results':results,'productionDatabaseWrites':0}))
finally:
    for name in names:subprocess.run(['docker','stop',name],capture_output=True)
