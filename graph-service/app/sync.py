"""Operator-only CLI; not exposed through HTTP or MCP."""
import json
from workflow_otel import setup,httpx_propagation
from opentelemetry import trace
from .source import collect,project
from .store import Store
setup('legacy-assistant-graph');httpx_propagation()
store=Store()
try:
    sources,chunks=collect(); projection=project(sources,chunks)
    store.schema();print(json.dumps(store.sync(projection)))
finally:
    store.driver.close()
    provider=trace.get_tracer_provider()
    if hasattr(provider,'force_flush'):provider.force_flush()
