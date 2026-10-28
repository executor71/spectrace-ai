"""Read-only final service, source-preservation and collector evidence checks."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def run(*args):return subprocess.check_output(args,stderr=subprocess.STDOUT).decode('utf8')
names=run('docker','ps','-a','--filter','label=com.docker.compose.project=master','--format','{{.Names}}').splitlines()
objects=json.loads(run('docker','inspect',*names))
before={c['service']:c for c in json.loads((OUT/'runtime-before.json').read_text(encoding='utf8'))['containers']}
rows=[]
for c in objects:
    service=c['Config']['Labels']['com.docker.compose.service']
    rows.append({'service':service,'name':c['Name'].lstrip('/'),'image':c['Config']['Image'],'imageId':c['Image'],
                 'status':c['State']['Status'],'exitCode':c['State']['ExitCode'],'startedAt':c['State']['StartedAt'],
                 'health':c['State'].get('Health',{}).get('Status'),'ports':c['NetworkSettings']['Ports']})
    if service=='analysis-model-init':assert c['State']['ExitCode']==0
    else:assert c['State']['Running'],service
    if service in {'postgres','neo4j','ollama','backend'}:assert c['State']['StartedAt']==before[service]['state']['StartedAt'],service
(OUT/'runtime-after.json').write_text(json.dumps({'capturedAt':datetime.now(timezone.utc).isoformat(),'containers':rows},indent=2),encoding='utf8')
network=subprocess.check_output(['docker','compose','exec','-T','ai-service','python','-'],input=(OUT/'network-probe.py').read_bytes()).decode('utf8')
(OUT/'network-final.json').write_text(network,encoding='utf8')
network=json.loads(network)
assert all(network['tcp'][name]=='OPEN' for name in ['otel-collector:4317','otel-collector:4318','jaeger:4317','jaeger:4318','jaeger:16686'])
code="from urllib.request import urlopen\nprint(urlopen('http://127.0.0.1:8888/metrics',timeout=3).read().decode())"
metrics=subprocess.check_output(['docker','run','-i','--rm','--network','container:master-otel-collector-1','master-ai-service','python','-'],input=code.encode()).decode('utf8')
(OUT/'collector-metrics-final.log').write_text(metrics,encoding='utf8')
with (OUT/'collector-validation.log').open('a',encoding='utf8') as f:f.write('\nFINAL AFTER REAL WORKFLOWS / OUTAGE RESTORED\n'+metrics)
for service in ['jaeger','otel-collector']:
    since=next(c['State']['StartedAt'] for c in objects if c['Config']['Labels']['com.docker.compose.service']==service)
    (OUT/(service+'-final.log')).write_text(run('docker','logs','--since',since,'master-'+service+'-1'),encoding='utf8')
starting=json.loads((OUT/'starting-worktree.json').read_text(encoding='utf8'))
changed=[rel for rel,digest in starting.items() if not (ROOT/rel).is_file() or hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest]
assert changed==['observability/python/workflow_otel/__init__.py'],changed
allowed={'compose.phase10.yaml','observability/python/workflow_otel/__init__.py','observability/python/workflow_otel/install.py','observability/tests/test_observability.py'}
diff=set(subprocess.check_output(['git','diff','--name-only','HEAD'],stderr=subprocess.DEVNULL).decode('utf8').splitlines())
assert not (diff-set(starting)-allowed),diff-set(starting)-allowed
assert (OUT/'otel-collector-config.yaml.before').read_bytes()==(ROOT/'observability/otel-collector-config.yaml').read_bytes()
assert (OUT/'jaeger-config.yaml.before').read_bytes()==(ROOT/'observability/jaeger-config.yaml').read_bytes()
preservation={'result':'PASS','changedPreexistingWorktreeFiles':changed,'permittedProductionAndTestChanges':sorted(allowed),
              'otherPreexistingChangesPreserved':True,'collectorConfigBytesUnchanged':True,'jaegerConfigBytesUnchanged':True,
              'businessSourcesPromptsGraphPolicyGroundTruthSchemaUnchanged':True,'postgresNeo4jOllamaBackendNeverRestarted':True,
              'gitCommit':False,'gitPush':False}
(OUT/'source-preservation.json').write_text(json.dumps(preservation,indent=2))
print(json.dumps({'servicesRunning':sum(row['status']=='running' for row in rows),'modelInitExitCode':0,'sourcePreservation':'PASS'}))
