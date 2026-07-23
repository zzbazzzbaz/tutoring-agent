import json

import httpx
import pytest

from teaching_agent.infrastructure.lightrag import LightRAGClient


@pytest.mark.asyncio
async def test_search_sends_expected_payload_and_returns_context():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://lightrag.test/query")
        payload = json.loads(request.content)
        assert payload["query"] == "TCP 三次握手"
        assert payload["mode"] == "mix"
        return httpx.Response(200, json={"response": "TCP 三次握手用于建立连接。"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = LightRAGClient(http_client, "http://lightrag.test/query")

        result = await client.search("TCP 三次握手")

    assert result == "TCP 三次握手用于建立连接。"
