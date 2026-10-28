"""Project real summary lines for video; no synthetic events, times or counts.

python -u docs/workflow-logging/video/watch-summary.py --follow
"""
import argparse
from pathlib import Path
import re
import sys
import subprocess


def project(line):
    if not re.search(r'\bstream=SUMMARY\b',line): return None
    fields=dict(re.findall(r'\b([A-Za-z]+)=([^\s]+)',line))
    stamp=re.search(r'\[\d{2}:\d{2}:\d{2}\]',line)
    if not stamp or not {'label','seq','status','result','service'} <= fields.keys(): return None
    source={'ai-service':'AI','backend':'BE','mcp-server':'MCP'}.get(fields['service'],fields['service'])
    content=f"{stamp[0]} {source} #{fields['seq']} {fields['label']}: {fields['status']} result={fields['result']}"
    # Keep the full identifier. seq is local to this service/run, never a fabricated global plan index.
    key='jobId' if fields.get('jobId','-')!='-' else 'traceId' if fields.get('traceId','-')!='-' else 'runId'
    content+=f" {key}={fields.get(key,'-')}"
    for key in ['mode','steps','toolName','provider','callScope','source','object','count','total','templates','conditions','testCases','mismatches','synthetic','httpStatus','operation','errorCode','attempt','model','durationMs','persistence']:
        if key in fields: content+=f" {key}={fields[key]}"
    return content


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-log',type=Path,help='Save unchanged summary rows separately.')
    parser.add_argument('--debug-log',type=Path,help='Save excluded ordinary logs separately.')
    parser.add_argument('--follow',action='store_true',help='Follow the actual three Compose services using the existing full configuration.')
    parser.add_argument('--tail',type=int,default=0,help='Existing lines per service when following (default: only new events).')
    args=parser.parse_args()
    raw=args.raw_log.open('a',encoding='utf8') if args.raw_log else None
    debug=args.debug_log.open('a',encoding='utf8') if args.debug_log else None
    child=None
    source=sys.stdin
    if args.follow:
        root=Path(__file__).resolve().parents[3]
        command=['docker','compose']
        for name in ['compose.yaml','compose.phase8.yaml','compose.phase9.yaml','compose.phase10.yaml','compose.phase11.yaml']:
            command+=['-f',str(root/name)]
        command+=['logs','-f','--tail',str(max(0,args.tail)),'--no-color','--no-log-prefix','ai-service','backend','mcp-server']
        child=subprocess.Popen(command,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace')
        source=child.stdout
    try:
        for line in source:
            view=project(line)
            target=raw if view else debug
            if target: target.write(line);target.flush()
            if view: print(view,flush=True)
    except KeyboardInterrupt: pass
    finally:
        if raw: raw.close()
        if debug: debug.close()
        if child and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
