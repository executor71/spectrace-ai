ARG BASELINE_IMAGE=master-ai-service:latest
FROM ${BASELINE_IMAGE}
WORKDIR /retrieval
COPY retrieval-service/requirements.txt ./requirements-phase8.txt
RUN pip install --no-cache-dir -r requirements-phase8.txt
COPY retrieval-service/retrieval ./retrieval
COPY retrieval-service/config ./config
ENV PYTHONPATH=/app:/retrieval
EXPOSE 8010
CMD ["uvicorn", "retrieval.api:app", "--host", "0.0.0.0", "--port", "8010"]
