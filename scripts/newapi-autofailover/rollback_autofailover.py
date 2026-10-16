"""Dry-run by default. Restore scoped configuration/containers, never restore business DBs."""
import pathlib,json,sys
source=pathlib.Path('/opt/canvas-newapi-autofailover-20261016/release_autofailover_r2.py').read_text();exec(source.split("assert not(rel/'started.json')")[0])
assert(rel/'completed.json').exists() and not(rel/'rolled-back.json').exists()
old=json.loads((rel/'before-containers-private.json').read_text());canvasBefore=json.loads((rel/'canvas-config-private.json').read_text());gatewayBefore=json.loads((rel/'native-config-private.json').read_text())
priceEntries={'ModelPrice':{'canvas-image':.03,'canvas-image-sunburst':.03,'canvas-qidong-flare':.03,'canvas-qidong-sunburst':.03},'ModelRatio':{'canvas-packy-flare':12.5,'canvas-packy-sunburst':12.5},'CompletionRatio':{'canvas-packy-flare':6,'canvas-packy-sunburst':6},'ImageRatio':{'canvas-packy-flare':1.6,'canvas-packy-sunburst':1.6}}
createdChannels=[];replaced=['canvas-migrated-api','new-api-personal','canvas-migrated-app']
for name in names:
 assert inspect(name)['Image']==expected[name]
 assert inspect(name+'-pre-autofailover-20261016-r2')['Id']==old[name]['Id'] and not inspect(name+'-pre-autofailover-20261016-r2')['State']['Running']
if '--execute-rollback' not in sys.argv:
 print(json.dumps({'dryRun':'PASS','rollbackContainersPresent':True,'onlyScopedModelsChannelsOptionsAndTokenLimitsRestored':True,'databaseRestore':False,'executeFlag':'--execute-rollback'}));sys.exit(0)
counts=node("import{sqlClient as s,closeDatabase}from'/app/dist/db/client.js';console.log(JSON.stringify((await s`select count(*)::int inflight from generation_tasks where status in ('queued','running')`)[0]));await closeDatabase();");assert counts['inflight']==0,'Wait for active work to finish before rollback'
# Restore configuration while current gateway is available. Keep quota consumption and all new business rows.
prefix=source.split('def rollback():',1)[1].split('\n for name in reversed(replaced):',1)[0]
exec('def restore_config_only():'+prefix)
restore_config_only()
for name in names:run(['docker','stop',name])
for name in names:run(['docker','rename',name,name+'-retained-after-autofailover-r2']);run(['docker','rename',name+'-pre-autofailover-20261016-r2',name])
run(['docker','start','new-api-personal']);wait('http://127.0.0.1:3044/api/status');run(['docker','start','canvas-migrated-api']);wait_api();run(['docker','start','canvas-migrated-app']);wait('https://canvas.dongyuanhub.com/');run(['docker','exec','canvas-migrated-app','nginx','-s','reload'])
(rel/'rolled-back.json').write_text(json.dumps({'at':time.time(),'businessDatabaseRestored':False,'newBusinessPreserved':True,'restored':names}));print(json.dumps({'rolledBack':True,'businessDatabaseRestored':False}))
