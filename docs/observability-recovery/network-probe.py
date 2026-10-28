"""Run in ai-service; read-only DNS, TCP, HTTP and collector metrics probe."""
import json
import socket
from urllib.request import build_opener, ProxyHandler

http=build_opener(ProxyHandler({}))
report={'dns':{},'tcp':{},'http':{}}
for name in ['otel-collector','jaeger','ai-service','backend']:
    try:report['dns'][name]=socket.gethostbyname(name)
    except OSError as error:report['dns'][name]=str(error)
for name,ports in [('otel-collector',[4317,4318,8888,13133]),('jaeger',[4317,4318,16686,13133])]:
    for port in ports:
        try:
            with socket.create_connection((name,port),timeout=2):report['tcp'][f'{name}:{port}']='OPEN'
        except OSError as error:report['tcp'][f'{name}:{port}']=str(error)
for url in ['http://otel-collector:13133/','http://otel-collector:8888/metrics','http://jaeger:16686/api/services','http://jaeger:13133/health/status']:
    try:
        with http.open(url,timeout=3) as response:
            body=response.read().decode();row={'status':response.status}
            if url.endswith('/metrics'):
                row['spanMetrics']=[line for line in body.splitlines() if not line.startswith('#') and any(key in line for key in ['accepted_spans','refused_spans','sent_spans','send_failed_spans','enqueue_failed_spans','queue_size','queue_capacity'])]
            report['http'][url]=row
    except Exception as error:report['http'][url]={'error':str(error)}
print(json.dumps(report,indent=2))
