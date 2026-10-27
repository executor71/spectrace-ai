import json,urllib.request,urllib.parse,hashlib,subprocess
from pathlib import Path
out=Path(__file__).resolve().parent;root=out.parents[1]
def get(url):
 with urllib.request.urlopen(url,timeout=30) as r:return json.load(r)
before=json.loads((out/'core-before.json').read_text(encoding='utf8'))
assert before=={path:get('http://localhost:8080'+path) for path in before}
initial=json.loads((out/'preexisting-worktree.json').read_text(encoding='utf-8-sig'))
allowed={'frontend/src/App.tsx','frontend/src/Icon.tsx','frontend/src/navigation.ts','backend/src/main/java/com/example/legacyassistant/testcase/TestCasePolicy.java'}
preserved=0
for item in initial['files']:
 if item['path'] in allowed:continue
 assert (root/item['path']).is_file(),item['path']+' missing'
 assert hashlib.sha256((root/item['path']).read_bytes()).hexdigest().upper()==item['sha256'].upper(),item['path']+' unexpectedly changed'
 preserved+=1
protected=['evaluation-service/datasets/ground-truth-v1.json','docs/phase11-evidence/relation-ground-truth.json','docs/phase11-evidence/multi-hop-evaluation.json','docs/phase11-evidence/hybrid-vs-graph-comparison.json','contracts/test-case-policy.json']
hashes={}
for name in protected:
 current=(root/name).read_bytes();committed=subprocess.check_output(['git','show','HEAD:'+name],cwd=root)
 assert current.replace(b'\r\n',b'\n')==committed.replace(b'\r\n',b'\n'),name+' changed'
 hashes[name]=hashlib.sha256(current).hexdigest()
expected={'change_impact.create','change_impact.baseline_load','change_impact.condition_diff','change_impact.rag_retrieve','change_impact.graph_traverse','change_impact.tc_match','change_impact.review','change_impact.export'}
found=set();traces=[]
for operation in expected:
 service='legacy-assistant-ai' if operation in {'change_impact.condition_diff','change_impact.rag_retrieve','change_impact.graph_traverse','change_impact.tc_match'} else 'legacy-assistant-backend'
 params=urllib.parse.urlencode(dict(service=service,operation=operation,lookback='1h',limit=5))
 for trace in get('http://localhost:16686/api/traces?'+params).get('data',[]):
  selected=[s for s in trace.get('spans',[]) if s['operationName'] in expected]
  if selected:
   found.update(s['operationName'] for s in selected)
   traces.append(dict(traceId=trace['traceID'],spans=[dict(name=s['operationName'],durationUs=s['duration'],tagKeys=[t['key'] for t in s.get('tags',[])]) for s in selected]))
summary=dict(coreUnchanged=True,preexistingFilesByteIdentical=preserved,preexistingFilesExtendedWithinScope=sorted(allowed),protectedFileHashes=hashes,spanNames=sorted(found),missingSpans=sorted(expected-found),traces=traces)
(out/'preservation-and-traces.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
assert not expected-found,expected-found
print(json.dumps({'coreUnchanged':True,'protectedFilesUnchanged':len(hashes),'spansFound':sorted(found)},ensure_ascii=True))
