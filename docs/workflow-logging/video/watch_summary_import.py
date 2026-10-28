"""Capture unchanged runtime stdout summary rows, plus a separate projection."""
import importlib.util
from pathlib import Path
import re
import subprocess

OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('video_projection',OUT/'watch-summary.py')
viewer=importlib.util.module_from_spec(spec);spec.loader.exec_module(viewer)


def capture(name,since,identifiers=None):
    records=[]
    for service in ['ai-service','backend','mcp-server']:
        raw=subprocess.check_output(['docker','logs','--timestamps','--since',since,'master-'+service+'-1'],stderr=subprocess.DEVNULL).decode('utf8')
        for stamped in raw.splitlines():
            stamp,line=stamped.split(' ',1)
            if 'stream=SUMMARY' in line and (not identifiers or any(identifier in line for identifier in identifiers)):
                records.append((stamp,line))
    # Historical docker logs are queried per container. Reconstruct their timeline
    # using real Docker timestamps, never by a desired event order.
    records.sort(key=lambda item:item[0])
    if not records: raise RuntimeError('No summary rows available; existing evidence was preserved')
    lines=[line for _,line in records]
    (OUT/(name+'.transport.log')).write_text('\n'.join(stamp+' '+line for stamp,line in records)+'\n',encoding='utf8')
    (OUT/(name+'.actual.log')).write_text('\n'.join(lines)+'\n',encoding='utf8')
    (OUT/(name+'.video.log')).write_text('\n'.join(filter(None,(viewer.project(line) for line in lines)))+'\n',encoding='utf8')
    return lines
