import json,urllib.request,subprocess
from pathlib import Path
out=Path('evaluation-guide-evidence');out.mkdir(exist_ok=True)
r=urllib.request.urlopen('http://localhost:5173/api/evaluations/targets');body=json.load(r);(out/'targets.json').write_text(json.dumps(body,indent=2),encoding='utf8');print(r.status,body)
sql="SELECT 'truth',md5(jsonb_agg(to_jsonb(g) ORDER BY dataset_version,case_id)::text) FROM evaluation.ground_truth g UNION ALL SELECT 'bindings',md5(jsonb_agg(to_jsonb(b) ORDER BY requirement_id,dataset_version,case_id)::text) FROM evaluation.requirement_binding b UNION ALL SELECT 'catalog',md5(jsonb_agg(to_jsonb(c) ORDER BY chunk_id)::text) FROM evaluation.evidence_catalog c;"
p=subprocess.run(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-c',sql],capture_output=True);assert p.returncode==0,p.stderr;(out/'frozen-before.txt').write_bytes(p.stdout);print(p.stdout.decode())
