"""Explicit administrative download; normal retrieval inference stays offline."""
from pathlib import Path
import hashlib,json,time
from huggingface_hub import snapshot_download
from retrieval.core import settings
cfg=settings()['reranker'];start=time.perf_counter()
snapshot=snapshot_download(repo_id=cfg['model'],revision=cfg['revision'],cache_dir=cfg['cacheDir'],
    allow_patterns=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','sentencepiece.bpe.model'],max_workers=2)
files=[]
for p in sorted(Path(snapshot).glob('*')):
    if p.is_file():
        digest=hashlib.sha256()
        with p.open('rb') as file:
            for chunk in iter(lambda:file.read(1024*1024),b''):digest.update(chunk)
        files.append({'file':p.name,'bytes':p.stat().st_size,'sha256':digest.hexdigest()})
print(json.dumps({'model':cfg['model'],'revision':cfg['revision'],'downloadAndChecksumMs':(time.perf_counter()-start)*1000,'totalBytes':sum(f['bytes'] for f in files),'files':files}))
