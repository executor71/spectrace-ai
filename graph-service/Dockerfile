FROM python:3.12-slim
WORKDIR /graph
COPY graph-service/requirements.txt /graph/requirements.txt
COPY observability/requirements.txt /graph/otel-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r otel-requirements.txt
COPY observability/python /opt/observability
COPY graph-service /graph
ENV PYTHONPATH=/graph:/opt/observability
USER 10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8030", "--no-access-log"]
