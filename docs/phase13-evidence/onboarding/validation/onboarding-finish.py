from pathlib import Path
import json,hashlib,difflib,shutil,re
root=Path('D:/MASTER과정');out=Path('onboarding-evidence');dest=root/'docs/phase13-evidence/onboarding'
baseline=json.loads((out/'baseline.json').read_text(encoding='utf8'))
for name,digest in baseline['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
files=[];diff=[]
for stage in Path('onboarding-stage').iterdir():
 current=root/'frontend/src'/stage.name;assert current.read_bytes()==stage.read_bytes();before=out/f'before-{stage.name}'
 old=before.read_text(encoding='utf8') if before.exists() else '';new=current.read_text(encoding='utf8')
 if old!=new:
  files.append('frontend/src/'+stage.name);diff.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='before/frontend/src/'+stage.name,tofile='after/frontend/src/'+stage.name))
 if before.exists():
  assert re.findall(r'fetch\([^\n]+',old)==re.findall(r'fetch\([^\n]+',new),stage.name
live=json.loads((out/'live-results.json').read_text(encoding='utf8'));ui=json.loads((out/'ui-results.json').read_text(encoding='utf8'));webkit=json.loads((out/'webkit-results.json').read_text(encoding='utf8'))
result={'scope':'React UI only; existing API routes, backend/AI/DB/evaluation rules unchanged','changedFiles':sorted(files),'features':['Exact requested one-sentence service purpose on landing page','Four numbered visual workflow steps; explicit next-step CTAs','Natural-language synthetic IT asset example fills title/description only; saving/analysis/generation/review/execution remain explicit user actions','Task-oriented navigation and screen titles; technical terms explained separately under technical validation/management','Korean cause-and-action guidance for absent analysis, held generation, unregistered evaluation, concurrent analysis','Elapsed-time progress and duplicate-request prevention for local LLM analysis','Existing dashboard, TC review, execution, saved evaluation, report download and graph lookup retained'],'build':'TypeScript/Vite build passed','protectedSourceFilesMatched':len(baseline['hashes']),'APIRequestExpressionsUnchanged':True,'realChromeFlow':live,'stateAndResponsiveChecks':ui,'mobileSafariSizedWebKitCheck':webkit,'savedEvaluation':json.loads((out/'saved-evaluation-results.json').read_text(encoding='utf8')),'progressAndRetryCheck':json.loads((out/'progress-results.json').read_text(encoding='utf8')),'limits':['Desktop Chrome and WebKit iPhone emulation were tested; physical iPhone Safari was not tested','No human usability study was conducted; tests verify visible purpose, steps and next actions','Local LLM output and existing source/template guards can hold generation. Earlier actual attempts and reasons are preserved; no guard or evaluation standard was changed','Validation uses existing API operations to create three synthetic demonstration requests and retained test records; no schema, data seeding, direct DB writes, or production system changes were performed'],'attempts':[{'directory':'short-example-attempt','summary':'Short initial example: related approval API source missing; generation safely held'},{'directory':'extended-example-attempt','summary':'API-heavy draft: local analysis retained a clarification question; generation safely held'},{'directory':'.','summary':'Final natural-language synthetic example uses the same request as an existing generated demonstration; actual result recorded in live-results.json'}]}
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');(out/'ui-only.diff').write_text(''.join(diff),encoding='utf8')
dest.mkdir(parents=True,exist_ok=True)
for p in out.iterdir():
 if p.is_dir():shutil.copytree(p,dest/p.name,dirs_exist_ok=True)
 elif p.name=='live-flow-blocked.png' and live['success']:continue
 elif not p.name.startswith('before-') or p.suffix=='.png':shutil.copy2(p,dest/p.name)
validation=dest/'validation';validation.mkdir(exist_ok=True)
for name in ['onboarding-live-flow.py','onboarding-ui-check.py','onboarding-webkit.py','onboarding-saved-evaluation.py','onboarding-progress-check.py','onboarding-finish.py']:shutil.copy2(name,validation/name)
manifest={str(p.relative_to(dest)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in dest.rglob('*') if p.is_file() and p.name!='manifest.json'}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print('Saved evidence:',len(manifest),'files; React source files:',len(files),'Live flow success:',live['success'])
