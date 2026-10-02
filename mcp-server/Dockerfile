FROM python:3.11-slim
WORKDIR /gateway
COPY mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp-server/app ./app
COPY ai-service/app/analysis_models.py ./app/contracts/analysis_models.py
RUN useradd --uid 10001 --create-home gateway
USER 10001
EXPOSE 8020
HEALTHCHECK --interval=10s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/health')"
CMD ["uvicorn", "app.server:application", "--host", "0.0.0.0", "--port", "8020", "--no-access-log"]
