import logging

import httpx

from app.config import get_settings


settings = get_settings()

logger = logging.getLogger(__name__)


class AgentServiceError(RuntimeError):
    pass


async def generate_with_agent(payload: dict) -> dict:
    """
    Send a generation request to the Pi Agent service.

    Local Ollama inference may be slow on CPU, especially for
    Ship30 responses (~1,250 words), so generation receives a
    generous read timeout.

    Connection failures still fail quickly.
    """

    timeout = httpx.Timeout(
        connect=10.0,
        read=600.0,
        write=30.0,
        pool=10.0,
    )

    try:
        logger.info(
            "Sending generation request to agent service",
            extra={
                "provider": payload.get("provider"),
                "mode": payload.get("mode"),
            },
        )

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.post(
                f"{settings.agent_service_url}/generate",
                json=payload,
            )

            response.raise_for_status()

            result = response.json()

            logger.info(
                "Agent generation completed",
                extra={
                    "provider": payload.get("provider"),
                    "mode": payload.get("mode"),
                },
            )

            return result

    except httpx.ReadTimeout as exc:
        logger.exception(
            "Agent generation timed out"
        )

        raise AgentServiceError(
            "MODEL_TIMEOUT"
        ) from exc

    except httpx.ConnectTimeout as exc:
        logger.exception(
            "Could not connect to agent service"
        )

        raise AgentServiceError(
            "AGENT_UNAVAILABLE"
        ) from exc

    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:1000]

        logger.exception(
            "Agent service returned an error"
        )

        raise AgentServiceError(
            f"AGENT_ERROR: {detail}"
        ) from exc

    except httpx.HTTPError as exc:
        logger.exception(
            "Agent service communication failed"
        )

        raise AgentServiceError(
            "AGENT_UNAVAILABLE"
        ) from exc