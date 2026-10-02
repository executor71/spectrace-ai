"""Administrative tokenizer-length audit; sends public query strings only, never labels."""
from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase8-evidence'
queries=[q['queryText'] for q in json.loads((dest/'evaluation-dataset.json').read_text(encoding='utf-8'))['queries']]
code='''
import json,sys
from transformers import AutoTokenizer
from huggingface_hub import snapshot_download
from retrieval.core import settings,corpus_snapshot
from app.db import rag_connection_settings
cfg=settings()['reranker'];snapshot=snapshot_download(repo_id=cfg['model'],revision=cfg['revision'],cache_dir=cfg['cacheDir'],local_files_only=True)
tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
queries=QUERY_TEXTS
corpus=corpus_snapshot(rag_connection_settings())['chunks']
lengths=tokenizer([[q,c['content'][:700]] for q in queries for c in corpus],truncation=False,return_length=True)['length']
assert max(lengths)<=cfg['maxLength']
assert max(len(c['content']) for c in corpus)<=700
print(json.dumps({'result':'PASS','queryCount':len(queries),'pairCount':len(lengths),'maxPairTokens':max(lengths),'configuredMaxLength':cfg['maxLength'],'truncatedPairs':0,'maxChunkCharacters':max(len(c['content']) for c in corpus),'snippetTruncation':False}))
'''.replace('QUERY_TEXTS',repr(queries))
result=subprocess.run(['docker','exec','-i','master-retrieval-service-1','python','-'],input=code.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
assert result.returncode==0,result.stderr.decode();(dest/'token-length-audit.json').write_bytes(result.stdout);print(result.stdout.decode())
