from unittest.mock import patch
from database import execute

def test_catalogo_ordenacao(app):
    # Insere motos com cenários variados no banco de dados temporário de testes
    # Moto 1: sem foto, fornecedor (ID 1)
    execute("""
        INSERT INTO motos (modelo, cor, origem, preco_aquisicao, preco_venda, vendido, fotos_url, km)
        VALUES ('Moto A', 'Vermelha', 'Fornecedor', 10000, 12500, 0, NULL, 0)
    """)
    # Moto 2: sem foto, própria (ID 2)
    execute("""
        INSERT INTO motos (modelo, cor, origem, preco_aquisicao, preco_venda, vendido, fotos_url, km)
        VALUES ('Moto B', 'Preta', 'Propria', 10000, 12500, 0, NULL, 0)
    """)
    # Moto 3: com foto, fornecedor (ID 3)
    execute("""
        INSERT INTO motos (modelo, cor, origem, preco_aquisicao, preco_venda, vendido, fotos_url, km)
        VALUES ('Moto C', 'Azul', 'Fornecedor', 10000, 12500, 0, 'https://drive.google.com/drive/folders/test1', 0)
    """)
    # Moto 4: com foto, própria (ID 4)
    execute("""
        INSERT INTO motos (modelo, cor, origem, preco_aquisicao, preco_venda, vendido, fotos_url, km)
        VALUES ('Moto D', 'Verde', 'Propria', 10000, 12500, 0, 'https://drive.google.com/drive/folders/test2', 0)
    """)
    # Moto 5: com foto, própria (ID 5 - mais recente)
    execute("""
        INSERT INTO motos (modelo, cor, origem, preco_aquisicao, preco_venda, vendido, fotos_url, km)
        VALUES ('Moto E', 'Branca', 'Propria', 10000, 12500, 0, 'https://drive.google.com/drive/folders/test3', 0)
    """)

    # Mockamos a API do Google Drive para que não tente fazer requisições reais
    with patch('blueprints.catalogo.list_gdrive_images') as mock_list_drive, \
         patch('blueprints.catalogo.render_template') as mock_render:
        
        # Simulamos que a função de listagem retorna uma foto fictícia para qualquer pasta existente
        mock_list_drive.return_value = ["http://fakeurl.com/photo.jpg"]
        mock_render.return_value = "html"

        with app.test_request_context():
            from blueprints.catalogo import catalogo_lista
            catalogo_lista()
            
            # Recupera os argumentos enviados para o render_template
            assert mock_render.called
            args, kwargs = mock_render.call_args
            motos_passadas = kwargs.get('motos', [])
            
            # Esperamos 5 motos na lista
            assert len(motos_passadas) == 5
            
            # Ordem esperada:
            # 1. Moto E (com foto, própria, ID 5)
            # 2. Moto D (com foto, própria, ID 4)
            # 3. Moto C (com foto, fornecedor, ID 3)
            # 4. Moto B (sem foto, própria, ID 2)
            # 5. Moto A (sem foto, fornecedor, ID 1)
            
            modelos_ordenados = [m['modelo'] for m in motos_passadas]
            assert modelos_ordenados == ['Moto E', 'Moto D', 'Moto C', 'Moto B', 'Moto A']
