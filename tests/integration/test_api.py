"""
tests/integration/test_api.py
Integration tests for FastAPI endpoints.
Requires: pytest-asyncio, httpx

Run: pytest tests/integration/ -v
"""
import io
import pytest
from httpx import AsyncClient, ASGITransport
from PIL import Image

# Import app only if env vars are set
try:
    from app.main import app
    APP_AVAILABLE = True
except Exception:
    APP_AVAILABLE = False


def create_dummy_image(text: str = "TEST DOCUMENT") -> bytes:
    """Create a simple white image with text for testing."""
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.skipif(not APP_AVAILABLE, reason="App not configured")
class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_root(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    @pytest.mark.asyncio
    async def test_health_check(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data


@pytest.mark.skipif(not APP_AVAILABLE, reason="App not configured")
class TestDocumentEndpoints:
    @pytest.mark.asyncio
    async def test_aadhaar_endpoint_accepts_image(self):
        img_bytes = create_dummy_image()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents/aadhaar/read",
                files={"file": ("aadhaar.jpg", img_bytes, "image/jpeg")},
                data={"use_ocr": "false"},
            )
        assert response.status_code in (200, 422)  # 422 = extraction failed (no real doc)
        data = response.json()
        assert "document_type" in data

    @pytest.mark.asyncio
    async def test_pan_endpoint_accepts_image(self):
        img_bytes = create_dummy_image()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents/pan/read",
                files={"file": ("pan.jpg", img_bytes, "image/jpeg")},
                data={"use_ocr": "false"},
            )
        assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_invalid_file_type_rejected(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents/aadhaar/read",
                files={"file": ("doc.exe", b"MZ\x90\x00binary", "application/octet-stream")},
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_expiry_validity_rules(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/documents/expiry/validity-rules")
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "income_certificate" in data["rules"]

    @pytest.mark.asyncio
    async def test_marksheet_invalid_class(self):
        img_bytes = create_dummy_image()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents/marksheet/read",
                files={"file": ("marks.jpg", img_bytes, "image/jpeg")},
                data={"exam_class": "99"},
            )
        assert response.status_code == 400
