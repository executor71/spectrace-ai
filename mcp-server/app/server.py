from contextlib import asynccontextmanager
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import json
import os
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from jsonschema import Draft202012Validator, FormatChecker
from mcp import types
from .clients import Services, GatewayError
from .schemas import INPUTS
from .tools import Gateway
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.shared.exceptions import McpError
from .contracts.analysis_models import AnalysisResult
from .schemas import UUID, strict
from starlette.middleware.trustedhost import TrustedHostMiddleware
from mcp.server.transport_security import TransportSecuritySettings
if os.getenv('APP_OTEL_ENABLED') == 'true':
    from workflow_otel import observed_tool, correlation, request_id as telemetry_request_id, attrs as telemetry_attrs
    from opentelemetry import trace as telemetry_trace
else:
    observed_tool = lambda function: function
    correlation = lambda: {}

ANALYSIS_SCHEMA = AnalysisResult.model_json_schema()
# Reference the original public schema without maintaining a second analysis model.
ANALYSIS_OUTPUT = strict({"analysis": {k: v for k, v in ANALYSIS_SCHEMA.items() if k != "$defs"},
    "analysisSource": {"enum": ["SAVED", "GENERATED"]}}, ["analysis", "analysisSource"])
ANALYSIS_OUTPUT["$defs"] = ANALYSIS_SCHEMA.get("$defs", {})

server = Server("legacy-tool-gateway", version="0.9.0")

@server.list_tools()
async def list_tools():
    return [types.Tool(name=name, description="Adapter to existing " + name + " service",
        inputSchema=schema, outputSchema=ANALYSIS_OUTPUT if name == "analyze_requirement" else None,
        annotations=types.ToolAnnotations(readOnlyHint=name not in {"analyze_requirement", "execute_approved_test"},
            destructiveHint=False, idempotentHint=name not in {"analyze_requirement", "execute_approved_test"}, openWorldHint=False))
        for name, schema in INPUTS.items()]

@server.call_tool(validate_input=False)
@observed_tool
async def call_tool(name, arguments):
    started, request_id = time.perf_counter(), str(uuid4())
    if os.getenv('APP_OTEL_ENABLED') == 'true':
        telemetry_request_id.set(request_id)
        telemetry_attrs(telemetry_trace.get_current_span(), {'requestId': request_id})
    stamp = datetime.now(timezone.utc).isoformat()
    status, code, downstream = "SUCCESS", None, {"search_knowledge": "ai/retrieval",
        "analyze_requirement": "backend", "get_test_cases": "backend", "get_evaluation_result": "evaluation",
        "execute_approved_test": "backend"}.get(name)
    try:
        if name not in INPUTS:
            raise GatewayError("UNKNOWN_TOOL")
        validator = Draft202012Validator(INPUTS[name], format_checker=FormatChecker())
        if not validator.is_valid(arguments):
            raise GatewayError("INVALID_ARGUMENTS")
        result = await getattr(gateway, name)(arguments)
        if name == "analyze_requirement":
            Draft202012Validator(ANALYSIS_OUTPUT).validate(result)
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))], structuredContent=result)
    except GatewayError as exc:
        status, code = "ERROR", exc.code
        downstream = exc.service or downstream
        error = {"errorCode": code, "requestId": request_id}
        return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=json.dumps(error))], structuredContent=error)
    except Exception:
        status, code = "ERROR", "INTERNAL_ERROR"
        error = {"errorCode": code, "requestId": request_id}
        return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=json.dumps(error))], structuredContent=error)
    finally:
        logging.getLogger("gateway").warning(json.dumps({**correlation(), "timestamp": stamp,
            "service": "legacy-assistant-mcp", "level": "INFO", "event": "mcp.tool",
            "toolName": name if name in INPUTS else "UNKNOWN_TOOL",
            "requestId": request_id, "startedAt": stamp, "durationMs": round((time.perf_counter()-started)*1000, 3),
            "resultStatus": status, "downstreamService": downstream, "errorCode": code}))

manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True,
    security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:8020", "localhost:8020", "mcp-server:8020"],
        allowed_origins=["http://127.0.0.1:8020", "http://localhost:8020"]))

@server.list_resource_templates()
async def resource_templates():
    return [types.ResourceTemplate(uriTemplate="requirement://{requirementId}", name="Requirement summary", mimeType="application/json")]

@server.read_resource()
async def read_resource(uri):
    value = str(uri)
    prefix = "requirement://"
    identifier = value[len(prefix):] if value.startswith(prefix) else ""
    if not Draft202012Validator(UUID, format_checker=FormatChecker()).is_valid(identifier):
        raise McpError(types.ErrorData(code=-32602, message="INVALID_RESOURCE_URI"))
    try:
        result = await gateway.requirement_resource(identifier)
        return [ReadResourceContents(content=json.dumps(result, ensure_ascii=False), mime_type="application/json")]
    except GatewayError as exc:
        raise McpError(types.ErrorData(code=-32002, message=exc.code)) from None

async def transport(scope, receive, send):
    await manager.handle_request(scope, receive, send)

async def health(request):
    return JSONResponse({"status": "UP", "service": "mcp-server"})

@asynccontextmanager
async def lifespan(app):
    global gateway
    async with httpx.AsyncClient(timeout=660, trust_env=False, follow_redirects=False) as client:
        gateway = Gateway(Services(client))
        async with manager.run():
            yield

application = Starlette(routes=[Route("/health", health), Mount("/mcp", app=transport)], lifespan=lifespan)
application.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "mcp-server"])
if os.getenv('APP_OTEL_ENABLED') == 'true':
    from workflow_otel.install import mcp
    mcp(application)
