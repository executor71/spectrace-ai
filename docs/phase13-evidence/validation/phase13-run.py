from pathlib import Path
import subprocess,sys,json
sys.stdout.reconfigure(encoding='utf8')
r=Path('D:/MASTER과정');out=Path('phase13-evidence').resolve();action=sys.argv[1]
def run(name,args):
 p=subprocess.run(args,cwd=r,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(out/name).write_bytes(p.stdout);print(name,p.returncode,p.stdout.decode('utf8',errors='replace')[-1800:]);return p.returncode
if action=='deploy':
 sys.exit(run('deploy.log',['docker','compose','-p','master','-f','compose.yaml','-f','compose.phase8.yaml','-f','compose.phase9.yaml','-f','compose.phase10.yaml','-f','compose.phase11.yaml','up','-d','--no-deps','backend','frontend']))
if action=='test':
 (out/'backend-junit').mkdir(exist_ok=True)
 override=out/'test-compose.json';override.write_text(json.dumps({'services':{'backend-test':{'volumes':[{'type':'bind','source':str(out/'backend-junit'),'target':'/workspace/target/surefire-reports'}]}}}),encoding='utf8')
 sys.exit(run('backend-tests.log',['docker','compose','-p','spectrace-phase13-tests','-f','compose.test.yaml','-f',str(override),'run','--build','--rm','backend-test']))
if action=='build':sys.exit(run('build-final.log',['docker','compose','-p','master','-f','compose.yaml','build','backend','frontend']))
