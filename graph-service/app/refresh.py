"""Best-effort committed REST snapshot refresh; never blocks Core transactions.

The existing operator projection remains the single mapping implementation.
No write/admin endpoint is exposed. Failed refreshes retain the previous graph.
"""
import hashlib
import json
import logging
import threading
import httpx
from .source import collect, project

class Refresher:
    def __init__(self, store, interval=10):
        self.store=store
        self.interval=interval
        self.stopped=threading.Event()
        self.states={}
        self.hashes={}

    def cycle(self):
        with httpx.Client(base_url='http://backend:8080', timeout=10, trust_env=False) as client:
            response=client.get('/api/dashboard/summary')
            response.raise_for_status()
            for req in response.json()['requirements']:
                rid=req['id']
                self.states.setdefault(rid, 'PENDING')
                try:
                    sources,chunks=collect(client=BorrowedClient(client), requirement_ids=[rid])
                    digest=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
                    if self.hashes.get(rid)!=digest:
                        self.store.sync(project(sources,chunks))
                        self.hashes[rid]=digest
                    self.states[rid]='SYNCED'
                except Exception:
                    self.states[rid]='FAILED'
                    logging.getLogger(__name__).warning('Graph snapshot refresh failed for %s',rid)

    def run(self):
        while not self.stopped.is_set():
            try:
                self.store.schema()
                self.cycle()
            except Exception:
                # Discovery/Neo4j failures are retried; cached good snapshots survive.
                for rid in self.states:self.states[rid]='FAILED'
                logging.getLogger(__name__).warning('Graph refresh unavailable; retrying')
            self.stopped.wait(self.interval)

class BorrowedClient:
    def __init__(self, client):self.client=client
    def __enter__(self):return self.client
    def __exit__(self,*args):return False
