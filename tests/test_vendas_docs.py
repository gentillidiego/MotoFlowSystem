import io
import pytest
from unittest.mock import patch, MagicMock
from app import app
from database import execute, query
from utils import User

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True
        yield client

def test_vendas_docs_requires_login(client):
    resp = client.get("/vendas/documentos/1")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location")

def test_vendas_docs_view_authenticated(auth_client):
    # Setup test sale
    execute("INSERT INTO motos (modelo, placa, preco_aquisicao, preco_venda, origem) VALUES ('Titan Teste', 'TTT1234', 8000, 10000, 'Usadas')")
    m = query("SELECT id FROM motos WHERE placa='TTT1234'", one=True)
    moto_id = m["id"]

    execute("INSERT INTO vendas (nome, telefone, produto_id, data_venda) VALUES ('Cliente Teste', '8299999999', ?, '2026-09-26')", (moto_id,))
    v = query("SELECT id FROM vendas WHERE nome='Cliente Teste'", one=True)
    venda_id = v["id"]

    with patch("blueprints.vendas.list_moto_documents") as mock_list:
        mock_list.return_value = {
            "categories": {}, "geral_files": [], "total_files": 0, "drive_url": None
        }
        resp = auth_client.get(f"/vendas/documentos/{venda_id}")
        assert resp.status_code == 200
        assert b"Cliente Teste" in resp.data
        assert b"Titan Teste" in resp.data

    # Cleanup
    execute("DELETE FROM vendas WHERE id=?", (venda_id,))
    execute("DELETE FROM motos WHERE id=?", (moto_id,))

def test_vendas_docs_vincular_authenticated(auth_client):
    execute("INSERT INTO vendas (nome, data_venda) VALUES ('Cliente Vincular', '2026-09-26')")
    v = query("SELECT id FROM vendas WHERE nome='Cliente Vincular'", one=True)
    venda_id = v["id"]

    with patch("blueprints.vendas.ensure_moto_doc_subfolders") as mock_ensure:
        mock_ensure.return_value = {}
        resp = auth_client.post(f"/vendas/documentos/{venda_id}/vincular", data={
            "drive_folder_input": "https://drive.google.com/drive/folders/1QOD-xIZ3RN7f7IBc7zRMLh4Q-jgVo0v4"
        })
        assert resp.status_code == 302
        assert f"/vendas/documentos/{venda_id}" in resp.headers.get("Location")

        updated = query("SELECT drive_doc_folder_id FROM vendas WHERE id=?", (venda_id,), one=True)
        assert updated["drive_doc_folder_id"] == "1QOD-xIZ3RN7f7IBc7zRMLh4Q-jgVo0v4"

    execute("DELETE FROM vendas WHERE id=?", (venda_id,))

def test_vendas_docs_criar_pasta_authenticated(auth_client):
    execute("INSERT INTO vendas (nome, data_venda) VALUES ('Cliente Criar Pasta', '2026-09-26')")
    v = query("SELECT id FROM vendas WHERE nome='Cliente Criar Pasta'", one=True)
    venda_id = v["id"]

    with patch("blueprints.vendas.create_venda_drive_folder") as mock_create:
        mock_create.return_value = "new_created_folder_id_789"
        resp = auth_client.post(f"/vendas/documentos/{venda_id}/criar-pasta")
        assert resp.status_code == 302

        updated = query("SELECT drive_doc_folder_id FROM vendas WHERE id=?", (venda_id,), one=True)
        assert updated["drive_doc_folder_id"] == "new_created_folder_id_789"

    execute("DELETE FROM vendas WHERE id=?", (venda_id,))

def test_vendas_docs_upload_in_memory(auth_client):
    execute("INSERT INTO vendas (nome, data_venda, drive_doc_folder_id) VALUES ('Cliente Upload', '2026-09-26', 'folder_123')")
    v = query("SELECT id FROM vendas WHERE nome='Cliente Upload'", one=True)
    venda_id = v["id"]

    with patch("blueprints.vendas.ensure_moto_doc_subfolders") as mock_sub, \
         patch("blueprints.vendas.upload_moto_document") as mock_upload:
        
        mock_sub.return_value = {"veiculo": {"id": "sub_veiculo_id", "name": "01_Documento_Veiculo"}}
        mock_upload.return_value = (True, None)

        data = {
            "categoria": "veiculo",
            "files": (io.BytesIO(b"fake pdf content in memory"), "documento.pdf")
        }
        resp = auth_client.post(f"/vendas/documentos/{venda_id}/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 302
        assert mock_upload.called
        # Verify uploaded bytes were passed directly in memory
        args, _ = mock_upload.call_args
        assert args[0] == b"fake pdf content in memory"
        assert args[1] == "documento.pdf"
        assert args[2] == "sub_veiculo_id"

    execute("DELETE FROM vendas WHERE id=?", (venda_id,))

def test_vendas_docs_download_streaming(auth_client):
    with patch("blueprints.vendas.stream_gdrive_file") as mock_stream:
        mock_stream.return_value = (iter([b"chunk1", b"chunk2"]), "application/pdf")
        resp = auth_client.get("/vendas/documentos/download/file_test_123?name=doc_original.pdf")
        assert resp.status_code == 200
        assert resp.data == b"chunk1chunk2"
        assert "attachment; filename=\"doc_original.pdf\"" in resp.headers.get("Content-Disposition")
