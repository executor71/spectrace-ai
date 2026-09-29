"""Offline CLI; emits a Flyway seed, does not connect to any database."""
import argparse
import json
import logging
import time
from pathlib import Path

from app.local_embedding import get_embedding_provider
from app.seed_export import export_seed

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    result = export_seed(args.corpus, get_embedding_provider(), args.output)
    result['elapsed_seconds'] = round(time.perf_counter()-started,3)
    args.output.with_suffix('.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
