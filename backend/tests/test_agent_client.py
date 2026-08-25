import pytest
import respx
import httpx
from app.services.agent import generate_with_agent
from app.config import get_settings


@pytest.mark.asyncio
async def test_agent_client_contract():
    url = f"{get_settings().agent_service_url}/generate"
    with respx.mock:
        respx.post(url).mock(return_value=httpx.Response(200, json={"text": "Grounded answer [S1]", "model": "test", "artifact": None}))
        result = await generate_with_agent({"message": "test"})
    assert result["text"].endswith("[S1]")
