from pathlib import Path
import subprocess,json,sys
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase6-evidence'
def run(args,name):
    with (dest/name).open('wb') as out:result=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT)
    assert result.returncode==0,(name,result.returncode)
compose=['docker','compose','-p','legacy-phase6-tests','-f',str(root/'compose.test.yaml'),'-f',str(root/'compose.phase6-test.yaml')]
run(compose+['up','-d','postgres-test'],'test-db-start.log')
run(compose+['run','--build','--rm','backend-test'],'backend-tests.log')
print('PASS Backend regression',flush=True)
run([sys.executable,str(root/'docs/scripts/phase6-seed.py'),'--test'],'test-seed.log')
run(compose+['run','--build','--rm','evaluation-test'],'evaluation-tests.log')
print('PASS Evaluation tests',flush=True)
