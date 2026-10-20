from pathlib import Path
import subprocess,json,sys,datetime,re,xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf8')
out=Path('phase13-evidence');p=Path('phase13-edge.py');s=p.read_text(encoding='utf8').replace('저장된 평가가 없습니다.','미평가: 저장된 평가 결과가 없습니다.');p.write_text(s,encoding='utf8')
# End state integrity: exact protected source files must match the starting commit.
root=Path('D:/MASTER과정');baseline=json.loads((out/'baseline.json').read_text(encoding='utf8'))
protected=['ai-service','retrieval-service','evaluation-service','mcp-server','graph-service','contracts','backend/src/main/resources/db/migration','backend/src/main/java/com/example/legacyassistant/testcase','backend/src/main/java/com/example/legacyassistant/analysis']
diff=subprocess.check_output(['git','diff',baseline['commit'],'--',*protected],cwd=root);assert not diff
start=datetime.datetime.fromtimestamp((out/'baseline.json').stat().st_mtime,datetime.timezone.utc).isoformat()
logs=subprocess.run(['docker','logs','--since',start,'master-ollama-1'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.decode('utf8',errors='replace')
llm_calls=len(re.findall(r'POST\s+"/api/(?:chat|generate)"',logs));assert llm_calls==0
tests=[]
for file in (out/'backend-junit').glob('TEST-*.xml'):
 suite=ET.parse(file).getroot();tests.append({k:suite.attrib.get(k) for k in ['name','tests','failures','errors','skipped']})
assert sum(int(s['tests']) for s in tests)==94
for suite in tests:assert int(suite['failures'])==int(suite['errors'])==0
result={'protectedSourceUnchanged':protected,'ollamaChatGenerateCallsSinceBaseline':llm_calls,'sinceUTC':start,'tests':tests,'gitStatus':subprocess.check_output(['git','status','--short'],cwd=root).decode('utf8')}
(out/'final-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('protected source unchanged; 94 tests passed; LLM calls:',llm_calls)
