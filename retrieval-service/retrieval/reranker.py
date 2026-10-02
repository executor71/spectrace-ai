"""Local cross-encoder provider. Inputs are query and candidate text only; no label interface."""
from typing import Protocol,Sequence
import time

class RerankerProvider(Protocol):
    def score(self,query:str,passages:Sequence[str])->list[float]:...

class LocalRerankerProvider:
    def __init__(self,config):
        if config['provider']!='local_transformers' or not config['model'] or not config['revision']:raise ValueError('Explicit local model and pinned revision required')
        if config['device']!='cpu' or min(config['batchSize'],config['maxLength'],config['cpuThreads'])<1:raise ValueError('Invalid local inference settings')
        self.config=config;self.model=None;self.tokenizer=None;self.load_ms=None

    def load(self):
        import torch
        from transformers import AutoModelForSequenceClassification,AutoTokenizer
        from huggingface_hub import snapshot_download
        start=time.perf_counter();cfg=self.config;torch.set_num_threads(cfg['cpuThreads'])
        snapshot=snapshot_download(repo_id=cfg['model'],revision=cfg['revision'],cache_dir=cfg['cacheDir'],local_files_only=True)
        self.tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
        model=AutoModelForSequenceClassification.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,torch_dtype=torch.float32)
        model.to(cfg['device']);model.eval();self.model=model;self.load_ms=(time.perf_counter()-start)*1000

    def score(self,query,passages):
        if not passages:return []
        if self.model is None:self.load()
        import torch
        scores=[];cfg=self.config
        for offset in range(0,len(passages),cfg['batchSize']):
            pairs=[[query,text] for text in passages[offset:offset+cfg['batchSize']]]
            tokens=self.tokenizer(pairs,padding=True,truncation=True,max_length=cfg['maxLength'],return_tensors='pt')
            with torch.inference_mode():
                values=self.model(**tokens,return_dict=True).logits.view(-1).float().cpu().tolist()
            scores.extend(values)
        return scores
