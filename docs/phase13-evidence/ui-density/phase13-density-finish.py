from pathlib import Path
import json,shutil,hashlib,subprocess
root=Path('D:/MASTER과정');out=Path('phase13-density-evidence');dest=root/'docs/phase13-evidence/ui-density'
before=json.loads((out/'before-measurements.json').read_text(encoding='utf8'));after=json.loads((out/'after-measurements.json').read_text(encoding='utf8'))
summary=[]
for old,new in zip(before,after):
 assert not new['overflow']
 assert max(c['height'] for c in new['cards'])-min(c['height'] for c in new['cards'])<0.1
 assert 110<=new['cards'][0]['height']<=140
 expected=4 if new['width']>=1440 else 2
 assert sum(abs(c['y']-new['cards'][0]['y'])<1 for c in new['cards'])==expected
 if new['width']>=1024:
  centers=[new[k]['y']+new[k]['height']/2 for k in ['select','refresh','register']];assert max(centers)-min(centers)<1
 if new['width']>=1440:assert new['charts']['bottom']<=new['viewportHeight']
 summary.append({'width':new['width'],'KPIColumns':expected,'toolbarHeightBefore':old['toolbar']['height'],'toolbarHeightAfter':new['toolbar']['height'],'KPIHeightBefore':old['cards'][0]['height'],'KPIHeightAfter':new['cards'][0]['height'],'chartsTopBefore':old['charts']['y'],'chartsTopAfter':new['charts']['y'],'chartsHeightBefore':old['charts']['height'],'chartsHeightAfter':new['charts']['height'],'pageOverflow':new['overflow'],'equalCardHeights':True})
changed=['frontend/src/dashboard.css','frontend/src/Dashboard.tsx']
result={'scope':'Phase 13 dashboard presentation only','changedSourceFiles':changed,'changes':['Dashboard-local selectors override inherited card padding, paragraph margins and button grid alignment without !important','Heading and tabs share one flex row with wrapping','Toolbar uses Grid; controls align on one row on desktop/tablet; timestamp stays inline on desktop and compact on a second row below 1180px','Sections use 20px gap; cards use 16–20px padding; KPI titles and numbers use 8px spacing','KPI content height is intrinsic, uniform across all grid rows; four columns desktop, two tablet/mobile, one below 360px','Chart/card/table padding and row spacing reduced; table scrolling and handlers preserved'],'measurements':summary,'verification':json.loads((out/'functional-check.json').read_text(encoding='utf8')),'build':'npm run build (tsc -b && vite build) passed via existing frontend Docker build','environment':'Installed Chrome, desktop viewport emulation; no real iPhone Safari test','screenshots':{'before':[f'before-{width}.png' for width in [1920,1440,1024,390]],'after':[f'after-{width}.png' for width in [1920,1440,1024,390]]},'unchanged':'149 backend/AI/RAG/evaluation/MCP/Graph/contracts/docker files hash matched; no service or DB modifications; existing uncommitted Phase 13 work preserved'}
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
# Preserve exact source edits separately from the pre-existing uncommitted work.
diff=[]
import difflib
for name in ['dashboard.css','Dashboard.tsx']:
 diff.extend(difflib.unified_diff((out/f'before-{name}').read_text(encoding='utf8').splitlines(True),(root/'frontend/src'/name).read_text(encoding='utf8').splitlines(True),fromfile=f'before/frontend/src/{name}',tofile=f'after/frontend/src/{name}'))
(out/'ui-only.diff').write_text(''.join(diff),encoding='utf8')
dest.mkdir(parents=True,exist_ok=True)
for p in out.iterdir():
 if p.is_file() and p.suffix not in ['.log'] or p.name in ['frontend-build.log','frontend-deploy.log']:
  shutil.copy2(p,dest/p.name)
for name in ['phase13-density-check.py','phase13-density-functional.py','phase13-density-finish.py']:shutil.copy2(name,dest/name)
files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in dest.iterdir() if p.is_file() and p.name!='manifest.json'}
(dest/'manifest.json').write_text(json.dumps(files,ensure_ascii=False,indent=2),encoding='utf8')
print('Verified four viewport layouts; saved',len(files),'evidence files')
