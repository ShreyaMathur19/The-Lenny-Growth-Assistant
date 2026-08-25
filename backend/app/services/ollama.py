import httpx
from app.config import get_settings

settings = get_settings()


class OllamaUnavailable(RuntimeError):
    pass


async def embed_texts(texts: list[str]) -> list[list[float]]:
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embedding_model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            if not embeddings:
                raise OllamaUnavailable("Ollama returned no embeddings")
            return embeddings
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaUnavailable(str(exc)) from exc


async def ollama_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            return response.is_success
    except httpx.HTTPError:
        return False
