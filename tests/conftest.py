import pytest
import os
import tempfile
from app import app as flask_app
from database import init_db, DB

@pytest.fixture
def app():
    # Caminho temporário para o banco de dados de teste
    db_fd, db_path = tempfile.mkstemp()
    flask_app.config.update({
        "TESTING": True,
        "DATABASE": db_path,
        "WTF_CSRF_ENABLED": False  # Desabilita CSRF para facilitar testes de POST
    })

    # Sobrescreve o caminho do DB no módulo database.py (gambiarra necessária para testar sem mudar muito o código)
    import database
    original_db = database.DB
    database.DB = db_path

    with flask_app.app_context():
        init_db()
        yield flask_app

    # Cleanup
    database.DB = original_db
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
