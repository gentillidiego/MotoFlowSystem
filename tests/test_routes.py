def test_home_page_requires_login(client):
    """Verifica se a home exige login (redireciona)"""
    response = client.get('/')
    assert response.status_code == 302
    assert b"/login" in response.data or "/login" in response.location

def test_estoque_requires_login(client):
    """Garante que o estoque exige login (redireciona)"""
    response = client.get('/estoque')
    assert response.status_code == 302
    assert "/login" in response.location

def test_vendas_requires_login(client):
    """Garante que vendas exige login"""
    response = client.get('/vendas')
    assert response.status_code == 302

def test_404_custom_page(client):
    """Verifica se a página 404 personalizada aparece"""
    response = client.get('/uma-rota-que-nao-existe')
    assert response.status_code == 404
    assert b"P\xc3\xa1gina N\xc3\xa3o Encontrada" in response.data or b"404" in response.data
