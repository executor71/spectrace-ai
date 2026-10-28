"""Stopped Jaeger store backup/working clone only; business volumes not mounted."""
import hashlib
import json
from pathlib import Path
import shutil

source=Path('/source')
targets=[Path('/backup'),Path('/work')]
manifest=[]
for path in sorted(source.rglob('*')):
    if path.is_file():
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        manifest.append({'path':path.relative_to(source).as_posix(),'bytes':path.stat().st_size,'sha256':digest.hexdigest()})
for target in targets:
    assert not list(target.iterdir()),'Refuse to overwrite an existing backup/clone'
    shutil.copytree(source,target,dirs_exist_ok=True)
report={'sourceVolume':'master_jaeger-data','backupVolume':'spectrace-jaeger-backup-20261028',
        'workingVolume':'spectrace-jaeger-work-20261028','files':manifest,'bytes':sum(item['bytes'] for item in manifest)}
Path('/evidence/store-backup.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'files':len(manifest),'bytes':report['bytes'],'backupVolume':report['backupVolume'],'workingVolume':report['workingVolume']}))
