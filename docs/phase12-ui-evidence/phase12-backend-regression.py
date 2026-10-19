import os
﻿import json,subprocess
from pathlib import Path
out=Path(os.environ.get('PHASE12_EVIDENCE_DIR',str(Path(__file__).resolve().parent))).resolve();(out/'backend-junit').mkdir(exist_ok=True)
r=Path('D:/MASTER과정');override=out/'backend-test-compose.json';override.write_text(json.dumps({'services':{'backend-test':{'volumes':[{'type':'bind','source':str(out/'backend-junit'),'target':'/workspace/target/surefire-reports'}]}}}),encoding='utf8')
p=subprocess.run(['docker','compose','-p','spectrace-phase12-tests','-f',str(r/'compose.test.yaml'),'-f',str(override),'run','--rm','backend-test'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(out/'backend-regression.log').write_bytes(p.stdout);print(p.returncode,p.stdout.decode(errors='replace')[-1600:]);assert p.returncode==0
