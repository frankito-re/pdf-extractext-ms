import pytest
from httpx import ASGITransport, AsyncClient

from presentation.main import app


async def get_root(root_path: str = ""):
    transport = ASGITransport(app=app, root_path=root_path)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/")


@pytest.mark.asyncio
async def test_root_redirige_a_docs_sin_prefijo():
    response = await get_root()

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


@pytest.mark.asyncio
async def test_root_respeta_el_root_path_del_proxy():
    response = await get_root(root_path="/api")

    assert response.status_code == 307
    assert response.headers["location"] == "/api/docs"
