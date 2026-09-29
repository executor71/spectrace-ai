"""Replaceable LLM provider, unrelated to the Phase 2 embedding provider."""
import json
import os
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


class LlmUnavailableError(RuntimeError):
    pass


class LlmProvider(Protocol):
    def generate(self, messages: list[dict], schema: dict) -> str: ...


class LocalLlmProvider:
    def __init__(self):
        self.url = os.getenv('ANALYSIS_LLM_URL', 'http://ollama:11434').rstrip('/')
        self.model = os.getenv('ANALYSIS_LLM_MODEL', 'qwen2.5:7b-instruct')
        self.timeout = float(os.getenv('ANALYSIS_LLM_TIMEOUT_SECONDS', '300'))

    def generate(self, messages: list[dict], schema: dict) -> str:
        thinking = os.getenv('ANALYSIS_LLM_THINK', 'false').lower() == 'true'
        # Ollama 0.11.10 + Qwen3 routes schema-constrained output into the thinking
        # channel when think=true. Supply the schema in the prompt instead;
        # the same strict Pydantic and grounding validators remain mandatory.
        payload = {'model': self.model, 'messages': messages, 'stream': False,
            'think': thinking, 'keep_alive': '10m',
            'options': {'temperature': 0, 'seed': 42, 'num_ctx': 12288, 'num_predict': 4096, 'num_thread': 4}}
        if not thinking:
            payload['format'] = schema
        body = json.dumps(payload).encode()
        try:
            request = Request(self.url + '/api/chat', data=body, headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
            if data.get('done') is not True or data.get('done_reason') == 'length':
                raise ValueError('Incomplete model response')
            content = data['message']['content']
            if not isinstance(content, str):
                raise ValueError('Invalid provider response')
            return content
        except (URLError, OSError, ValueError, KeyError) as error:
            raise LlmUnavailableError('Local analysis model is unavailable or did not finish') from error
