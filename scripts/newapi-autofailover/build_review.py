import hashlib,json,os,pathlib,subprocess,tarfile
os.umask(0o077);root=pathlib.Path('/opt/canvas-newapi-autofailover-20261016');target=root/'review-candidate';target.mkdir(mode=0o700,exist_ok=True)
def run(a):return subprocess.check_output(a,stderr=subprocess.PIPE)
baseline=json.loads((root/'before-private.json').read_text())
for name in ['canvas-migrated-api','canvas-migrated-app']:
    before=next(x for x in baseline if x['Name']=='/'+name);current=json.loads(run(['docker','inspect',name]))[0];assert current['Id']==before['Id'] and current['Image']==before['Image']
with tarfile.open(root/'review-payload.tar.gz') as archive:
    for m in archive.getmembers():assert (target/m.name).resolve().is_relative_to(target.resolve()) and not m.issym() and not m.islnk()
    archive.extractall(target)
manifest=json.loads((root/'candidate-manifest.json').read_text())
for file,expected in manifest['files'].items():assert hashlib.sha256((target/file).read_bytes()).hexdigest()==expected
tags={}
for kind,base,tag,copy in [('api','infinite-canvas-api:newapi-images-20261016','infinite-canvas-api:autofailover-candidate-20261016','COPY canvas-dist/ /app/dist/\n'),('web','infinite-canvas:newapi-images-20261016','infinite-canvas:autofailover-candidate-20261016','COPY frontend/ /usr/share/nginx/html/\nRUN chmod -R a+rX /usr/share/nginx/html\n')]:
    dockerfile=target/('Dockerfile.'+kind);dockerfile.write_text('FROM '+base+'\n'+copy)
    (target/(kind+'-build.log')).write_bytes(run(['docker','build','-f',str(dockerfile),'-t',tag,str(target)]));tags[kind]={'tag':tag,'id':json.loads(run(['docker','image','inspect',tag]))[0]['Id']}
tags['gateway']={'tag':'new-api:canvas-autofailover-candidate','id':json.loads(run(['docker','image','inspect','new-api:canvas-autofailover-candidate']))[0]['Id']}
result={'images':tags,'deployed':False,'gatewayBinarySha256':manifest['gatewayBinarySha256'],'canvasApiFilesReplaced':['newapi-evidence.js','newapi-settlement.js']};(root/'candidate-images.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
