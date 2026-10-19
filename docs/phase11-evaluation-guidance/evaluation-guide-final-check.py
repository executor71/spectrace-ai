import subprocess,json,shutil
from pathlib import Path
out=Path('evaluation-guide-evidence');r=Path('D:/MASTER\uacfc\uc815')
sql="SELECT 'truth',md5(jsonb_agg(to_jsonb(g) ORDER BY dataset_version,case_id)::text) FROM evaluation.ground_truth g UNION ALL SELECT 'bindings',md5(jsonb_agg(to_jsonb(b) ORDER BY requirement_id,dataset_version,case_id)::text) FROM evaluation.requirement_binding b UNION ALL SELECT 'catalog',md5(jsonb_agg(to_jsonb(c) ORDER BY chunk_id)::text) FROM evaluation.evidence_catalog c;"
p=subprocess.run(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-c',sql],capture_output=True);assert p.returncode==0,p.stderr;(out/'frozen-after.txt').write_bytes(p.stdout);assert p.stdout==(out/'frozen-before.txt').read_bytes()
print('Frozen truth, bindings, evidence catalog: identical before/after')
base=['docker','compose','-p','spectrace-evaluation-guide-tests','-f',str(r/'compose.test.yaml'),'-f',str((out/'test-compose-override.json').resolve())]
p=subprocess.run(base+['down'],capture_output=True);(out/'test-cleanup.log').write_bytes(p.stdout+p.stderr);assert p.returncode==0
