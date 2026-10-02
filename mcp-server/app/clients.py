"""Fixed HTTP destinations only. No database drivers or caller supplied URLs."""
import httpx

DESTINATIONS = {"backend": "http://backend:8080", "ai": "http://ai-service:8000",
                "retrieval": "http://retrieval-service:8010", "evaluation": "http://evaluation-service:8090"}

class GatewayError(Exception):
    def __init__(self, code, service=None):
        self.code, self.service = code, service
        super().__init__(code)

class Services:
    def __init__(self, client):
        self.client = client

    async def request(self, service, method, path, body=None, missing=False):
        try:
            kwargs = {"json": body} if body is not None else {}
            response = await self.client.request(method, DESTINATIONS[service] + path, **kwargs)
        except httpx.TimeoutException:
            raise GatewayError("DOWNSTREAM_TIMEOUT", service) from None
        except httpx.HTTPError:
            raise GatewayError("DOWNSTREAM_UNAVAILABLE", service) from None
        if response.status_code == 404:
            if missing:
                return None
            raise GatewayError("NOT_FOUND", service)
        if not 200 <= response.status_code < 300:
            code = "DOWNSTREAM_ERROR"
            if response.status_code == 409:
                try:
                    candidate = response.json().get("code") or response.json().get("errorCode")
                    if candidate in {"NOT_APPROVED", "NOT_EXECUTABLE", "FIXTURE_NOT_READY", "API_NOT_ALLOWED"}:
                        code = candidate
                except ValueError:
                    pass
            raise GatewayError(code, service)
        try:
            return response.json()
        except ValueError:
            raise GatewayError("INVALID_DOWNSTREAM_RESPONSE", service) from None
