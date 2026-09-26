import io
import pytest
from unittest.mock import patch, MagicMock
from app import app
from database import execute, query
from utils import optimize_image_bytes, DOC_CATEGORIES, format_doc_item

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_doc_categories_structure():
    assert len(DOC_CATEGORIES) == 5
    keys = [c["key"] for c in DOC_CATEGORIES]
    assert "veiculo" in keys
    assert "codigo_seguranca" in keys
    assert "comprador" in keys
    assert "vendedor" in keys
    assert "vistoria" in keys

def test_optimize_image_bytes():
    from PIL import Image
    # Create a small dummy in-memory image
    img = Image.new("RGB", (2000, 2000), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    original_bytes = buf.getvalue()

    optimized_bytes, mime = optimize_image_bytes(original_bytes, max_dim=800, quality=75)
    assert mime == "image/jpeg"
    assert len(optimized_bytes) < len(original_bytes)
    
    # Verify resized dimension
    res_img = Image.open(io.BytesIO(optimized_bytes))
    assert max(res_img.size) <= 800

def test_format_doc_item():
    fake_file = {
        "id": "abc123id",
        "name": "crlv_2026.pdf",
        "mimeType": "application/pdf",
        "size": "204800",
        "createdTime": "2026-08-20T15:30:00.000Z"
    }
    item = format_doc_item(fake_file, "veiculo")
    assert item["id"] == "abc123id"
    assert item["is_pdf"] is True
    assert item["is_image"] is False
    assert "200.0 KB" in item["size_fmt"]
    assert item["created_date"] == "20/08/2026"
    assert "download" in item["download_url"]

def test_vincular_pasta_drive_route(client):
    # Setup test moto
    execute("INSERT INTO motos (modelo, placa, preco_aquisicao, preco_venda, origem) VALUES ('Teste Drive', 'TST9999', 10000, 12000, 'Propria')")
    m = query("SELECT id FROM motos WHERE placa='TST9999'", one=True)
    moto_id = m["id"]

    with patch("blueprints.estoque.ensure_moto_doc_subfolders") as mock_ensure:
        mock_ensure.return_value = {}
        # Test vinculate without login (redirect to login)
        resp = client.post(f"/estoque/documentos/{moto_id}/vincular", data={"drive_folder_input": "https://drive.google.com/drive/folders/fakefolderid123456789"})
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location")

    # Cleanup
    execute("DELETE FROM motos WHERE id=?", (moto_id,))
