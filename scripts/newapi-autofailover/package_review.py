import argparse,hashlib,json,pathlib,tarfile
script=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--artifact-dir',default=str(script));args=parser.parse_args()
root=pathlib.Path(args.artifact_dir).resolve()
canvas=script.parents[1] if (script.parents[1]/'api/src').is_dir() else script.parent/'canvas-newapi-worktree'
files={}
with tarfile.open(root/'review-payload.tar.gz','w:gz') as out:
    for name in ['newapi-evidence.js','newapi-settlement.js']:
        source=canvas/'api/dist'/name;out.add(source,arcname='canvas-dist/'+name);files['canvas-dist/'+name]=hashlib.sha256(source.read_bytes()).hexdigest()
    out.add(canvas/'web/dist',arcname='frontend')
    for source in sorted((canvas/'web/dist').rglob('*')):
        if source.is_file():files['frontend/'+source.relative_to(canvas/'web/dist').as_posix()]=hashlib.sha256(source.read_bytes()).hexdigest()
manifest={'gatewayBinarySha256':hashlib.sha256((root/'new-api-canvas-autofailover').read_bytes()).hexdigest(),'files':files,'deployed':False}
(root/'candidate-manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({'files':len(files),'archiveBytes':(root/'review-payload.tar.gz').stat().st_size}))
