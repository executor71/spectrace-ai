"""Read-only inventory. Save only whitelisted configuration, never credentials."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)
compose=['docker','compose']
for name in ['compose.yaml','compose.phase8.yaml','compose.phase9.yaml','compose.phase10.yaml','compose.phase11.yaml']:
    compose+=['-f',str(ROOT/name)]


def run(args):return subprocess.check_output(args,stderr=subprocess.STDOUT).decode('utf8',errors='replace')


names=run(['docker','ps','-a','--filter','label=com.docker.compose.project=master','--format','{{.Names}}']).splitlines()
containers=json.loads(run(['docker','inspect',*names]))
allowed={'APP_OTEL_ENABLED','OTEL_EXPORTER_OTLP_TRACES_ENDPOINT','OTEL_EXPORTER_OTLP_ENDPOINT','OTEL_EXPORTER_OTLP_PROTOCOL',
         'OTEL_TRACES_SAMPLER','OTEL_TRACES_SAMPLER_ARG','OTEL_SERVICE_NAME','OTEL_RESOURCE_ATTRIBUTES','OTEL_TRACES_EXPORTER',
         'WORKFLOW_SUMMARY_LOG','ANALYSIS_LLM_MODEL','ANALYSIS_LLM_URL','ANALYSIS_LLM_TIMEOUT_SECONDS'}
rows=[]
for container in containers:
    config=container['Config'];env=dict(value.split('=',1) for value in config.get('Env',[]) if '=' in value)
    rows.append({'name':container['Name'].lstrip('/'),'service':config['Labels'].get('com.docker.compose.service'),
                 'image':config['Image'],'imageId':container['Image'],'state':container['State'],
                 'composeFiles':config['Labels'].get('com.docker.compose.project.config_files'),
                 'command':config.get('Cmd'),'entrypoint':config.get('Entrypoint'),
                 'environment':{key:value for key,value in env.items() if key in allowed},
                 'ports':container['NetworkSettings']['Ports'],
                 'networks':{key:{'IPAddress':value['IPAddress'],'Aliases':value.get('Aliases')} for key,value in container['NetworkSettings']['Networks'].items()},
                 'mounts':[{'type':mount['Type'],'source':mount['Source'],'destination':mount['Destination'],'name':mount.get('Name'),'readWrite':mount['RW']} for mount in container['Mounts']]})
(OUT/'runtime-before.json').write_text(json.dumps({'capturedAt':datetime.now(timezone.utc).isoformat(),'containers':rows},ensure_ascii=False,indent=2),encoding='utf8')
for service in ['jaeger','otel-collector']:
    (OUT/(service+'-before.log')).write_text(run(['docker','logs','--tail','120','master-'+service+'-1']),encoding='utf8')
for rel in ['compose.phase10.yaml','observability/jaeger-config.yaml','observability/otel-collector-config.yaml']:
    shutil.copy2(ROOT/rel,OUT/(Path(rel).name+'.before'))
paths=run(['git','ls-files','-m','-o','--exclude-standard']).splitlines()
hashes={rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in paths if (ROOT/rel).is_file() and not rel.startswith('docs/observability-recovery/')}
(OUT/'starting-worktree.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([{'service':row['service'],'image':row['image'],'status':row['state']['Status']} for row in rows]))
