import httpx
from app.config import get_settings

settings = get_settings()


class AgentServiceError(RuntimeError):
    pass


async def generate_with_agent(payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{settings.agent_service_url}/generate", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as exc:
        raise AgentServiceError("MODEL_TIMEOUT") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise AgentServiceError(f"AGENT_ERROR: {detail}") from exc
    except httpx.HTTPError as exc:
        raise AgentServiceError("AGENT_UNAVAILABLE") from exc
